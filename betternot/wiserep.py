#!/usr/bin/env python3

import datetime
import json
import logging
import os
import sys
import time
from collections import OrderedDict
from pathlib import Path

import requests
import yaml
from astropy.io import ascii
from betternot import credentials
from betternot.fritz import radec

TNS_TOKEN = credentials.get_password(service="tns_token")
TNS_BOT_ID = "115364"
TNS_BOT_NAME = "ZTF_DESY"
WISEREP_TOKEN = credentials.get_password(service="wiserep_token")
WISEREP_BOT_ID = "1234"
WISEREP_BOT_NAME = "OKC_ZTF"


class Wiserep:
    """Upload a spectrum to WISeREP"""

    def __init__(self, ztf_id: str, spec_path: Path | str, sandbox: bool = True):
        super(Wiserep, self).__init__()
        self.logger = logging.getLogger()
        self.ztf_id = ztf_id
        self.spec_path = Path(spec_path)

        if sandbox:
            self.wiserep_endpoint = "https://sandbox.wiserep.org/api"
        else:
            self.wiserep_endpoint = "https://www.wiserep.org/api"

        self.ra, self.dec = radec(self.ztf_id)

        self.tns_name = self.query_tns()

        if self.tns_name is not None:
            server_filename = self.upload_files([self.spec_path])[0]
            self.read_spectrum(server_filename=server_filename)
            self.generate_report()
            self.send_metadata()

    def query_tns(self):
        """
        Check if the object is known on TNS (so we can use the ID on WISeREP, I have not figured out how to do a WISeREP cone search.)
        """
        queryurl_tns = "https://www.wis-tns.org/api/get/search"

        tns_marker = (
            'tns_marker{"tns_id": "'
            + str(TNS_BOT_ID)
            + '", "type": "bot", "name": "'
            + TNS_BOT_NAME
            + '"}'
        )
        headers = {"User-Agent": tns_marker}

        get_obj = {
            "ra": self.ra,
            "dec": self.dec,
            "radius": 3,
            "units": "arcsec",
        }

        json_file = json.dumps(get_obj)

        # I have no idea why the token is not in the header
        get_data = {"api_key": TNS_TOKEN, "data": json_file}

        response = requests.post(queryurl_tns, headers=headers, data=get_data)

        res_json = response.json()
        reply = res_json["data"]["reply"]

        if len(reply) > 0:
            tns_name = reply[0]["objname"]
            self.logger.info(f"Found match on TNS: {tns_name}")
        else:
            tns_name = None

            self.logger.info("Found no match on TNS.")

        return tns_name

    def read_spectrum(self, server_filename:str|None=None):
        """
        Open the spectrum ascii file and extract metadata
        """
        data = ascii.read(self.spec_path, names=("WAVE", "FLUX", "FLUX_ERR"))
        meta = data.meta["comments"]
        metadict = {}

        for entry in meta:
            keyval = entry.split("=")
            if len(keyval) > 1:
                key = keyval[0]
                val = keyval[1]
                if key == "HOME_OBSERVER":
                    observer = val
                    metadict.update({"observer": val})
                elif key == "REDUCER":
                    metadict.update({"reducer": val})
                elif key == "INTTIME":
                    metadict.update({"exptime": val})
                elif key == "DATE-OBS":
                    metadict.update({"obsdate": val.replace("T", " ")})
        
        if server_filename is not None:
            metadict.update({"ascii_file": server_filename})
        else:
            metadict.update({"ascii_file": str(self.spec_path)})

        # Let's assume the last modification time of the spectrum file is the reduction time
        timestamp = self.spec_path.stat().st_mtime
        reducedate = str(datetime.datetime.fromtimestamp(timestamp))
        metadict.update({"reduction_date": reducedate})

        self.metadata = metadict

    def generate_report(self, tns_name: str|None=None):
        """
        Open and fill the template spectrum report with the metadata of the spectrum
        """
        template_path = Path(__file__).parent.parent / "data" / "template.yaml"
        with open(template_path, "r") as stream:
            report = yaml.safe_load(stream)

        for key, val in self.metadata.items():
            report["objects"][0]["spectra"]["spectra_group"][0][key] = val

        if tns_name is None:
            tns_name = self.tns_name
        
        report["objects"][0]["iau_name"] = tns_name
        report["objects"][0]["ra"] = self.ra
        report["objects"][0]["decl"] = self.dec

        self.report = report

    def upload_files(self, file_list: list[Path]) -> list|None:
        """
        Upload a file to WISErEP and check the response
        """
        self.logger.info(f"Uploading {' '.join(str(x) for x in file_list)} to the WISeREP")
        url = self.wiserep_endpoint + "/file-upload"

        headers = {
            "User-Agent": 'tns_marker{"tns_id":'
            + str(WISEREP_BOT_ID)
            + ', "type":"bot",'
            ' "name":"' + WISEREP_BOT_NAME + '"}'
        }

        # api key data
        api_data = {"bot_api_key": WISEREP_TOKEN}
        # construct a dictionary of files and their data
        files_data = {}
        for i, path in enumerate(file_list):
        #     file_name = list_of_files[i]
        #     file_path = os.path.join(files_folder, file_name)
            key = "files[" + str(i) + "]"
            val = (str(path), open(path), "text/plain")
            files_data[key] = val

        response = requests.post(
            url, headers=headers, data=api_data, files=files_data
        )
        
        if response.status_code == 200:
            server_filenames = response.json()["data"]
            self.logger.debug(f"Received and saved as {server_filenames} on the WISeREP server")
            return server_filenames
        else:
            self.logger.warn(f"Something went wrong. Reponse code: {response.status_code}")
            return None
    
    # function for sending json metadata
    def send_json_report(self, json_report: dict):

        report_url = self.wiserep_endpoint + "/bulk-report"
        # headers
        headers = {
            "User-Agent": 'tns_marker{"tns_id":' + str(WISEREP_BOT_ID) + ', "type":"bot",'
            ' "name":"' + WISEREP_BOT_NAME + '"}'
        }


        payload = {"bot_api_key": WISEREP_TOKEN, "data": json_report}

        response = requests.post(report_url, headers=headers, data=payload)

        if response.status_code == 200:
            return response.json()
        else:
            self.logger.warn(f"Something went wrong. Reponse code: {response.status_code}")
            return None
    
    def send_metadata(self, report: str | None = None):
        """
        Send the metadata for a spectrum to WISeREP
        """
        if report is None:
            report = self.report

        json_report = json.dumps(report)
        
        res = self.send_json_report(json_report=json_report)
        print(res)

    # time.sleep(TIME_SLEEP)
    # response = upload_files(url, list_of_files)
    # response_check = check_response(response)
    # time.sleep(TIME_SLEEP)
    # # if files are uploaded
    # if response_check == True:
    #     logger.info("\nThe following files were uploaded on the WISeREP : \n")
    #     time.sleep(TIME_SLEEP)
    #     # response as json data
    #     json_data = response.json()
    #     # list of uploaded files
    #     uploaded_files = json_data["data"]
    #     for i in range(len(uploaded_files)):
    #         logger.info(f"filename: {str(uploaded_files[i])}")

    #     time.sleep(TIME_SLEEP)
    #     return uploaded_files
    # else:
    #     logger.info("\nFiles were not uploaded to the WISeREP.\n")
    #     time.sleep(TIME_SLEEP)
    #     return False