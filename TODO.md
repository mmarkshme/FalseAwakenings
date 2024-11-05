* stepping through Nick's code, run the example with the given logs
* once comfortable with the code and how it works, try to use with the basestation
    * ssh into basestation 
        * IP: 10.5.32.216
        * `ssh root@10.5.32.216`
        * enable fingerprint: type `yes`
        * Password: Hme@Nexeo2020
        * `cd /`
        * `cd SYSTEM/logs/enc/voice_engine`
        * `cat voice_engine`
    * write script to parse for on tomes of the headsets (how long has the headset been on -- assuming there's an off time as well)
    * find false triggers (see if command was registered as successful after, if it was a success message = successfully registered, if gibberish, false trigger) <- reference Nick's code