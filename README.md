## Pre-Requisites to run:
1. Log files for M4 and Voice Engine are downloaded and unzipped locally

## Possible issues/Re-work Needed:
1. Base_Ext logs start and end time will not always equal each other. To find the time frame, need to look at the *first* line of **base_ext.log(start)** and *last* line of **base_ext.6.log(end)**. Then compare to what voice engine log shows.
2. This script just prints the false awakenings count and uptime per headset to the console. *If you want rates and historical data, this will need to be stored and calculated.* 

<br/>

**How to Run:** `python -m false_awakening --m4_log_path <path to m4 base_ext logs> --ve_log_path <path to voice engine logs>`