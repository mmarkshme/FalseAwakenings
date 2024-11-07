import os
import re
import datetime
import argparse
import subprocess


#############LOG PARSING FUNCTIONS####################

####extracts timestamp from log line for all logs coming from base version 3.5 and up
def extract_timestamp_common(log_entry):
    timestamp_str = log_entry[0:21]
    return datetime.datetime.strptime(timestamp_str, '%y/%m/%d %H:%M:%S.%f')


###extracts timestamp from m4 log line dynamically, independent of base version
def extract_timestamp_m4(log_entry):
    if log_entry[0] == '[':
        timestamp_str = log_entry.split(']')[0][1:]
        return datetime.datetime.strptime(timestamp_str, '%m/%d/%y %H:%M:%S.%f')
    else:
        return extract_timestamp_common(log_entry)

###returns the contents of a file in one big string
def get_file_contents_as_string_variable(file_path):
    content = ''
    if os.path.exists(file_path):
        with open(file_path) as f:
            lines = f.readlines()
            content = content.join(lines)
    return content

###finds all lines that match a certain regex pattern
def find_matching_lines_regex(log_name, patterns):
    lines = []
    with open(log_name) as f:
        for line in f:
            for pattern in patterns:
                if re.search(pattern, line):
                    lines.append(line)
                    break
    return lines

###sorts a list of log lines by timestamp
###NOTE: can sort out of order in the case two log lines land on the same second
def sort_list_by_timestamp(log_name, lines):
    sorted_lines = []
    if log_name == "base_ext":
        sorted_lines = sorted(lines, key=extract_timestamp_m4)
    return sorted_lines

###removes consecutive duplicates from a list of log lines
###USAGE: for m4 logs only that have been sorted by regex match.
###lines is a list of log lines for m4
def remove_consecutive_duplicates(lines):
        prev_line = ""
        new_lines = []
        for line in lines:
            if prev_line not in line:
                new_lines.append(line)

            if "disconnected" in line:
                prev_line = "disconnected"
            if "VehDet0" in line:
                prev_line = "VehDet0"
            if ": 0 0 1" in line:
                prev_line = ": 0 0 1"

        return new_lines

###returns a list of log lines that contain a certain keyword
def get_log_lines_by_keyword(log_name, keywords):
    lines = []
    with open(log_name) as f:
        f = f.readlines()
        for line in f:
            for keyword in keywords:
                if keyword in line:
                    lines.append(line)
                    break
    return lines

###returns an entire log as a list of lines
def get_log_lines_as_list(file_path):
    # assigning lines as an empty list, to avoid nonetype error
    lines = []
    if os.path.exists(file_path):
        with open(file_path, errors='ignore') as f:
            lines = f.readlines()
    return lines

###returns all voice engine logs as a single string
def get_all_voice_logs_as_str(path_to_ve_logs):
    # Get all file names in the folder
    all_files_in_path = os.listdir(path_to_ve_logs)

    # Only look for voice_engine logs
    all_logs = [path_to_ve_logs + log for log in all_files_in_path if "voice_engine" in log]

    # Concatenate all logs into a single string
    all_logs_in_str = ""
    for log in all_logs:
        all_logs_in_str = all_logs_in_str + "\n" + get_file_contents_as_string_variable(log)

    return all_logs_in_str

###parses all voice logs by delimeter, returns a list of voice sessions as string chunk
def parse_all_voice_logs_by_voice_session(logs_as_str):
    all_sessions = logs_as_str.split("-------------------  Starting Voice Processing  -------------------------")
    all_sessions = all_sessions[1:]
    all_sessions = [session.split("\n") for session in all_sessions]
    return all_sessions
#################################################################

#############DATA PROCESSING FUNCTIONS####################

###gets the difference between two timestamps (session end and session start) in seconds and returns as string
def process_duration(voice_session_data):
    voice_session_data["Duration"] = str(
        datetime.datetime.strptime(voice_session_data["Session End"],
                          "%m/%d/%y %H:%M:%S") - datetime.datetime.strptime(
            voice_session_data["Session Start"], "%m/%d/%y %H:%M:%S"))

###processes the most likely outcome of a voice session
def process_most_likely_outcome(voice_session_data):
    valid_responses = ["lane two", "lane one", "line two", "line one", "volume up", "volume down"]

    ###REJECTS AND TIMEOUTS
    ###If VE thought nothing was said and the duration is less than 10 seconds, it is a reject
    if voice_session_data["What VE thought was said"] == "":
        if len(voice_session_data["Subsequent Actions Taken"]) == 2:
            if "'fail_earcon'" in voice_session_data["Subsequent Actions Taken"]:
                if voice_session_data["Duration"] < "0:00:10":
                    voice_session_data["Most Likely Outcome"] = "Reject"
                else:
                    voice_session_data["Most Likely Outcome"] = "Timeout"
        else:
            if voice_session_data["Duration"] < "0:00:10":
                voice_session_data["Most Likely Outcome"] = "Reject-User Not Notified"
            else:
                voice_session_data["Most Likely Outcome"] = "Timeout-User Not Notified"

    ###ONE TO ONE CALLS
    ###If VE attempted a call, it is a one to one call
    elif "'attempt_call'" in voice_session_data["Subsequent Actions Taken"] or "'lookup_user'" in \
            voice_session_data["Subsequent Actions Taken"]:
        voice_session_data["Most Likely Outcome"] = "One to One Call"
    ###USER NOT FOUND
    ###If VE attempted to call a user that was not found, it is a user not found
    elif "'user_not_found_command'" in voice_session_data["Subsequent Actions Taken"]:
        voice_session_data["Most Likely Outcome"] = "User Not Found"
    ###BOT CALLS
    ###If VE attempted a bot call, it is a bot call
    elif "'attempt_bot_call'" in voice_session_data["Subsequent Actions Taken"]:
        voice_session_data["Most Likely Outcome"] = "Bot Call"
    ###VOLUME CHANGE
    ###If VE attempted to change the volume, it is a volume change
    elif "'increment_volume_up'" in voice_session_data[
        'Subsequent Actions Taken'] or "'increment_volume_down'" in voice_session_data[
        "Subsequent Actions Taken"] or "'change_volume_level'" in voice_session_data[
        "Subsequent Actions Taken"]:
        voice_session_data["Most Likely Outcome"] = "Volume Change"
    ###LANE CHANGE
    ###If VE attempted to change lanes, it is a lane change
    elif "'connect_lane_one'" in voice_session_data[
        'Subsequent Actions Taken'] or "'connect_lane_two'" in voice_session_data[
        "Subsequent Actions Taken"] or "'change_lane'" in voice_session_data[
        "Subsequent Actions Taken"] or "'lookup_lane'" in voice_session_data[
        "Subsequent Actions Taken"]:
        voice_session_data["Most Likely Outcome"] = "Lane Change"
    ###No Action From VE
    ###If VE thought something was said, but it was not a valid response, VE takes no action
    elif any(
            response in voice_session_data["What VE thought was said"].lower() for response in valid_responses) or (
            voice_session_data["What VE thought was said"].lower().split()[0] == "call" and len(
            voice_session_data["What VE thought was said"].split()) == 2):
        voice_session_data["Most Likely Outcome"] = "No Action From VE"


###gets all headset on off lines from m4 logs and sorts them chronologically
####PP[1-9][0-9]* disconnected = headset disconnected from rfp
####: 0 0 1 = headset connected to rfp
####VehDet0\s+\(DisabledState\)\s+processing\s+EarlyWarn\s+Mode = headset disconnected from rfp
def get_all_base_ext_headset_connected_duration(M4_log_path):

    all_logs = os.listdir(M4_log_path)

    all_logs = [M4_log_path + log for log in all_logs if "base_ext" in log]
    all_on_off = []
    for log in all_logs:
        on_off = find_matching_lines_regex(log, [r"PP[1-9][0-9]* disconnected", ": 0 0 1",
                                                      "VehDet0\s+\(DisabledState\)\s+processing\s+EarlyWarn\s+Mode"])
        all_on_off = all_on_off + on_off

    all_on_off = sort_list_by_timestamp("base_ext", all_on_off)

    for line in all_on_off:
        if "but thinks it is still" in line:
            all_on_off.remove(line)

    all_on_off = remove_consecutive_duplicates(all_on_off)

    return all_on_off



###converts the log lines into a list of dicts with headset ID, state, and time
def process_data_set_for_duration(log_list):
        # initialize dictionary with headset IDs as key, nested key is date, and duration as value, starting at 0
        headset_dict = []

        # loop through each line in logs again
        # if the line contains 'established' get the time as unix epoch and sum to dict value with headset ID as key
        # if the line contains 'disconnected' get the time as unix epoch and sum to dict value with headset ID as key
        this_id = None
        last_state = None
        for line in log_list:
            this_timestamp = extract_timestamp_m4(line)

            if ': 0 0 1' in line:
                if last_state != 'on':
                    this_id = line.split('Headset')[1].split(':')[0]
                    headset_dict.append({"hs_id": this_id, "state": "on", "time": this_timestamp})
                    last_state = 'on'

            elif 'disconnected' in line or 'VehDet0' in line:
                if last_state != 'off':
                    if this_id is not None:
                        headset_dict.append({"hs_id": this_id, "state": "off", "time": this_timestamp})
                        last_state = 'off'

        return headset_dict

###parses voice sessions list into a list of dicts with session start, session end, duration, what VE thought was said, headset ID, subsequent actions taken, and most likely outcome
def get_voice_session_data(voice_session_list: list):
    voice_session_data = {"Session Start": "", "Session End": "", "Duration": "", "What VE thought was said": "",
                          "Headset ID": "",
                          "Subsequent Actions Taken": [], "Most Likely Outcome": "Other"}
    actions_taken = []

    for line in voice_session_list:
        try:
            if line != "":
                if "Wake word detected" in line:
                    voice_session_data["Session Start"] = line[1:18]
                if "Headset ID:" in line:
                    voice_session_data["Headset ID"] = line.split("Headset ID: ")[1].split()[0].replace("'", "")
                if "waitForInput: Result: Text:" in line:
                    voice_session_data["What VE thought was said"] = line.split("waitForInput: Result: Text: ")[1]
                if "Finished processing the command id" in line:
                    actions_taken.append(line.split("Finished processing the command id ")[1])
                if "ASR Recorder#0 is busy" in line:
                    voice_session_data["Session End"] = line[1:18]
                    process_duration(voice_session_data)
                    voice_session_data["Most Likely Outcome"] = "Reject"

                if "Exiting voice transaction worker thread" in line:
                    if voice_session_data["Session Start"] == "":
                        break
                    else:
                        voice_session_data["Session End"] = line[1:18]
                        process_duration(voice_session_data)
                        voice_session_data["Subsequent Actions Taken"] = actions_taken

                        process_most_likely_outcome(voice_session_data)
                        break
                if line == voice_session_list[-1]:
                    if line == "" and len(voice_session_list) > 1:
                        voice_session_data["Session End"] = voice_session_list[-2][1:18]
                    else:
                        voice_session_data["Session End"] = line[1:18]
                    voice_session_data["Subsequent Actions Taken"] = actions_taken
                    process_duration(voice_session_data)
                    process_most_likely_outcome(voice_session_data)

        except ValueError as e:
            print(f"Error parsing line: {line}")
            print(f"Voice Session Data: {str(voice_session_data)}")


    if voice_session_data["Session Start"] == "":
        return None
    else:
        return voice_session_data

###extracts and sums false awakenings from voice data
def extract_false_awakenings(voice_data):
    false_awakenings_data = {voice_data['Headset ID']: 0 for voice_data in voice_data if voice_data['Headset ID'] != ""}

    for data in voice_data:
        if data['Headset ID'] != "":
            if data['Most Likely Outcome'] == 'Other' or data['Most Likely Outcome'] == 'Timeout':
                false_awakenings_data[data['Headset ID']] += 1

    return false_awakenings_data

###gets the total uptime for each headset from the durations list
def get_total_uptime_per_headset(durations, last_ts):
    headset_uptimes = {duration["hs_id"]: 0 for duration in durations}
    for duration in durations:
        if duration["state"] == "on":
            headset_uptimes[duration["hs_id"]] -= int(duration["time"].timestamp())
        else:
            headset_uptimes[duration["hs_id"]] += int(duration["time"].timestamp())

    for key in headset_uptimes:
        if headset_uptimes[key] < 0:
            headset_uptimes[key] += int(last_ts.timestamp())

    return headset_uptimes

###gets the last timestamp from the headset logs, needed for calculating total uptime
def get_last_ts_headset(m4_path):
    last_log = m4_path + "base_ext.log"

    last_line = get_log_lines_as_list(last_log)[-1]

    return extract_timestamp_m4(last_line)

#################################################################

#############MAIN FUNCTIONS####################

###gets all headset data
###return all iterations of the data. From raw log lines ->  processed durations -> total uptimes
def get_hs_durations(m4_log_path):
    print("Getting Headset Log Lines as a list...")
    headset_on_off_raw_list = get_all_base_ext_headset_connected_duration(m4_log_path)
    print("Reformatting log lines to dictionaries...")
    durations_dict = process_data_set_for_duration(headset_on_off_raw_list)
    last_ts = get_last_ts_headset(m4_log_path)
    print("Calculating Uptimes per headset ID...")
    uptimes = get_total_uptime_per_headset(durations_dict, last_ts)
    print("Headset Uptimes(Seconds): ")
    print(uptimes)
    return headset_on_off_raw_list, durations_dict, uptimes

###gets all voice data
###returns full lifecycle of data. From raw log as string ->  list of voice sessions -> voice data with classifications -> false awakenings determinations
def get_false_awakening_data(path_to_ve_logs):
    print("Getting Voice Engine Logs as a single string...")
    ##put voice engine log into a single string
    all_logs_in_str = get_all_voice_logs_as_str(path_to_ve_logs)


    print("Parsing String as list of voice sessions...")
    ##parse voice engine logs
    all_voice_sessions = parse_all_voice_logs_by_voice_session(all_logs_in_str)

    print("Processing Voice Data...")
    voice_data = []
    for session in all_voice_sessions:
        this_session_data = get_voice_session_data(session)

        if this_session_data is not None:
            voice_data.append(this_session_data)

    print("Extracting False Awakenings...")
    false_awakening_data = extract_false_awakenings(voice_data)

    print("False Awakenings: ")
    print(false_awakening_data)
    return all_logs_in_str, all_voice_sessions, voice_data, false_awakening_data


if __name__ == '__main__':
    # parser = argparse.ArgumentParser(description='Process False Awakenings')
    # parser.add_argument('--m4_log_path', type=str)
    # parser.add_argument('--ve_log_path', type=str)
    # args = parser.parse_args()

    ##get headset on off list
    m4_log_path = 'C://Users//mmarks//MykahFiles//Projects//FalseAwakenings//SYSTEM//logs//enc//m4//'
    path_to_ve_logs = 'C://Users//mmarks//MykahFiles//Projects//FalseAwakenings//SYSTEM//logs//enc//voice_engine//'
   
    # m4_log_path = args.m4_log_path
    # path_to_ve_logs = args.ve_log_path

    # print("M4 Log Path: " + m4_log_path)
    # print("Voice Engine Log Path: " + path_to_ve_logs)

    command = ['python', '-m', 'false_awakening', '--m4_log_pth', m4_log_path, '--ve_log_path', path_to_ve_logs]

    subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    ##process headset durations
    print("--------------------PROCESSING HEADSET DATA-------------------")
    raw_list, durations_dict, uptimes = get_hs_durations(m4_log_path)

    ##get voice data
    print("--------------------PROCESSING VOICE DATA-------------------")
    voice_logs_as_str, all_voice_sessions_list, voice_data_dict, false_awakening_data = get_false_awakening_data(path_to_ve_logs)

    # See which headset data overlaps
    common_ids = []
    unique_ids = []
    for key in false_awakening_data:
        for headset in durations_dict:
            hs_id = headset['hs_id']
            if hs_id == key:
                if hs_id not in common_ids:
                    common_ids.append(hs_id)
    print(f'\nThere are {len(common_ids)} headsets that have both an uptime and false_awakenings:\n{common_ids}')

    # Extract hs_ids from uptimes
    uptime_ids = {entry['hs_id'] for entry in durations_dict if isinstance(entry, dict)}

    # Initialize list to store unique IDs
    unique_ids = []

    # Find unique IDs
    for key in false_awakening_data:
        if key not in uptime_ids and isinstance(false_awakening_data[key], dict) and false_awakening_data[key].get('details', 0) != 0:
            unique_ids.append(key)

    print(f'\nThere are {len(unique_ids)} headsets that have false awakenings AND NO uptime:\n{unique_ids}')

    