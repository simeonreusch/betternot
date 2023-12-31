# betterNOT
Toolset for preparing observations with the Nordic Optical Telescope (NOT). Currently only set up to work with ZTF transients. You need [Fritz](https://fritz.science) credentials.

The observability code is largely based on the [`NOT Observing Tools`](https://github.com/steveschulze/NOT_Observing_Tools) by Steve Schulze.

[![CI](https://github.com/simeonreusch/betternot/actions/workflows/continous_integration.yml/badge.svg)](https://github.com/simeonreusch/betternot/actions/workflows/continous_integration.yml)
[![PyPI version](https://badge.fury.io/py/betternot.svg)](https://badge.fury.io/py/betternot)

Note the [observation guidelines](https://notes.simeonreusch.com/s/dHt_0XzwQ#).

## Installation
Simply run `pip install betternot`.

If you want to make local changes, clone the repository, `cd` into it and issue `poetry install`.

## Usage
### Prepare observations
The observation planning can be run with a command line interface. Simply issue
```
not ZTF23changeit ZTF23thistoo ...
```
This will generate a standard star observability plot, create an observability plot for all ZTF objects, download the finding charts for them from Fritz and print the coordinates as well as the last observed magnitude for easy transfer to the triggering page. All plots are stored in a `betternot/DATE` directory. 

Optionally, you can specify a desired observing date with `-date YYYY-MM-DD` (the default is today). You can also specify a telescope site with `-site SITE` (available sites are listed [here](https://github.com/astropy/astropy-data/blob/gh-pages/coordinates/sites.json)). Default is the NOT site (Roque de los Muchachos).

### Uploading a spectrum to WISeREP
You will need a [TNS](https://www.wis-tns.org) and [WISeREP](https://www.wiserep.org) bot token for this. Uploading a spectrum can be done as follows:

```python
import logging
from betternot.wiserep import Wiserep

logging.basicConfig()
logger = logging.getLogger()
logger.setLevel(logging.DEBUG)

Wiserep(
    ztf_id="ZTF23aaawbsc",
    spec_path="ZTF23aaawbsc_combined_3850.ascii",
    sandbox=True, # set False for actual upload
    quality="high", # "low", "medium" or "high". Default: "medium"
)
```
This will check TNS if an IAU object exists at the ZTF transient location, open the spectrum, extract the metadata, and upload the file to WISeREP as well as a report containing the extracted metadata.

After checking with the [WISeREP sandbox](https://sandbox.wiserep.org) that everything worked fine, set `sandbox=False` to upload for good.