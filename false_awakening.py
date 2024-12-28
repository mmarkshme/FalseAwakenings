import os
import re
from pathlib import Path
from datetime import datetime, timedelta
from matplotlib import pyplot as plt


#############LOG PARSING FUNCTIONS####################

####extracts timestamp from log line for all logs coming from base version 3.5 and up
def extract_timestamp_common(log_entry):
    timestamp_str = log_entry[0:21]
    return datetime.strptime(timestamp_str, '%y/%m/%d %H:%M:%S.%f')


###extracts timestamp from m4 log line dynamically, independent of base version
def extract_timestamp_m4(log_entry):
    if log_entry[0] == '[':
        timestamp_str = log_entry.split(']')[0][1:]
        return datetime.strptime(timestamp_str, '%m/%d/%y %H:%M:%S.%f')
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
    all_logs = []

    # Walk through the directory tree
    for root, dirs, files in os.walk(path_to_ve_logs):
        # print(f"Current directory: {root}")
        # print(f"Files: {files}")
        for file in files:
            # print(f"Checking file: {file}")
            if "voice_engine" in file:
                # print(f"Found matching file: {file}")
                all_logs.append(os.path.join(root, file))

    # Concatenate all logs into a single string
    all_logs_in_str = ""
    for log in all_logs:
        all_logs_in_str += "\n" + get_file_contents_as_string_variable(log)

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
        datetime.strptime(voice_session_data["Session End"],
                          "%m/%d/%y %H:%M:%S") - datetime.strptime(
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

    # if 8 < int(voice_session_data["Headset ID"]) < 18:
    #     outcome = voice_session_data["Most Likely Outcome"]
        # if outcome is "Other" or outcome is "Timeout":
    # print(f'{voice_session_data["Headset ID"]}, {voice_session_data["What VE thought was said"]}, {voice_session_data["Subsequent Actions Taken"]}, {voice_session_data["Session Start"]}, {voice_session_data["Most Likely Outcome"]}, {voice_session_data["Duration"]}')

###gets all headset on off lines from m4 logs and sorts them chronologically
####PP[1-9][0-9]* disconnected = headset disconnected from rfp
####: 0 0 1 = headset connected to rfp
####VehDet0\s+\(DisabledState\)\s+processing\s+EarlyWarn\s+Mode = headset disconnected from rfp
def get_all_base_ext_headset_connected_duration(M4_log_path):
    all_logs = []
    all_data = []
    all_on_off = set()

    # Print the directory being searched
    # print(f"Searching in directory: {M4_log_path}")

    # Walk through the directory tree
    for root, dirs, files in os.walk(M4_log_path):
        # print(f"Current directory: {root}")
        # print(f"Files: {files}")
        for file in files:
            # print(f"Checking file: {file}")
            if "base_ext" in file:
                # print(f"Found matching file: {file}")
                all_logs.append(os.path.join(root, file))

    for log in all_logs:
        on_off = find_matching_lines_regex(log, [r"PP[1-9][0-9]* disconnected", ": 0 0 1",
                                                 "VehDet0\s+\(DisabledState\)\s+processing\s+EarlyWarn\s+Mode"])
        all_on_off.update(on_off)
        all_data.append(get_file_contents_as_string_variable(log))

    all_on_off = sort_list_by_timestamp("base_ext", all_on_off)

    for line in all_on_off:
        if "but thinks it is still" in line:
            all_on_off.remove(line)

    # all_on_off = remove_consecutive_duplicates(all_on_off)

    return all_on_off, all_data

###converts the log lines into a list of dicts with headset ID, state, and time
def process_data_set_for_duration(headset_on_off_raw_list, all_data, start_date, end_date):
    # Initialize dictionary with headset IDs as key, nested key is date, and duration as value, starting at 0
    headset_dict = {}
    on_pattern = 'Headset([0-9]+): 0 0 1'
    off_pattern = 'PP([0-9]+) disconnected$'

    # Convert start_date and end_date to datetime objects
    start_date = datetime.strptime(start_date, "%Y-%m-%d %H:%M:%S")
    end_date = datetime.strptime(end_date, "%Y-%m-%d %H:%M:%S")

    # Loop through each line in logs
    for index, line in enumerate(headset_on_off_raw_list):
        this_timestamp = extract_timestamp_m4(line)

        # Check if the timestamp is within the specified date range
        if start_date <= this_timestamp <= end_date:
            on_match = re.findall(on_pattern, line)
            if on_match:
                hs_id = on_match[0]
                if hs_id not in headset_dict:
                    headset_dict[hs_id] = {"on": [], "off": [], "events": []}
                if not any(entry['timestamp'] == this_timestamp for entry in headset_dict[hs_id]["on"]):
                    headset_dict[hs_id]["on"].append({"timestamp": this_timestamp, "line": line})
                    headset_dict[hs_id]["events"].append({"type": "on", "timestamp": this_timestamp, "line": line})

            off_match = re.findall(off_pattern, line)
            if off_match:
                hs_id = off_match[0]
                if hs_id in headset_dict:  # Only add off time if hs_id exists
                    if not any(entry['timestamp'] == this_timestamp for entry in headset_dict[hs_id]["off"]):
                        headset_dict[hs_id]["off"].append({"timestamp": this_timestamp, "line": line})
                        headset_dict[hs_id]["events"].append({"type": "off", "timestamp": this_timestamp, "line": line})

    # print(f'\nBefore removing duplicates:'); notify_on_matches(headset_dict, all_data)

    # Remove back-to-back 'on' and 'off' entries with the younger timestamp
    headset_dict = remove_back_to_back_entries(headset_dict)

    # Update ordered_events after removing duplicates
    ordered_events = []
    for hs_id in headset_dict:
        ordered_events.extend(headset_dict[hs_id]["events"])
    ordered_events.sort(key=lambda x: x["timestamp"])

    # print('\nAfter removing duplicates:'); notify_on_matches(headset_dict, all_data)

    return headset_dict

def get_all_data_between_ons(all_data, first_event, second_event, filename):
    r_all_between = f'({first_event}([\s\S]*){second_event})'
    output_dir = Path('GeneratedFiles')
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / filename

    for log in all_data:
        matches = re.findall(r_all_between, log, re.MULTILINE)
        if matches:
            with open(output_path, 'w') as file:
                all_data_between_events = matches[0][0]
                file.write(all_data_between_events + '\n')


def notify_on_matches(headset_dict, all_data):
    # Notify for back-to-back on_matches and capture data between them
    total_btb_ons = 0
    total_btb_offs = 0
    for hs_id, data in headset_dict.items():
        events = data["events"]
        on_count = 0
        off_count = 0
        for i in range(1, len(events)):
            if events[i]["type"] == "on" and events[i - 1]["type"] == "on":
                on_count += 1
                total_btb_ons += 1
                filename = f'(consecutive_on_event_{total_btb_ons}.txt)'
                first_event = events[i - 1]["line"].replace('\n', '').replace("/",'\/').replace('[','\[').replace(']', '\]')
                second_event = events[i]["line"].replace('\n', '').replace("/",'\/').replace('[','\[').replace(']', '\]')
                first_event_time = events[i - 1]['timestamp']
                second_event_time = events[i]['timestamp']
                # print(f"Alert: Back-to-back on_matches for headset {hs_id} at {first_event_time} and {second_event_time}")
                get_all_data_between_ons(all_data, first_event, second_event, filename)
            elif events[i]["type"] == "off" and events[i - 1]["type"] == "off":
                off_count += 1
                total_btb_offs += 1
                filename = f'(consecutive_off_event_{total_btb_offs}.txt)'
                first_event = events[i - 1]["line"].replace("/",'\/').replace('[','\[').replace(']', '\]')
                second_event = events[i]["line"].replace("/",'\/').replace('[','\[').replace(']', '\]')
                first_event_time = events[i - 1]['timestamp']
                second_event_time = events[i]['timestamp']
                # print(f"Alert: Back-to-back off_matches for headset {hs_id} at {first_event_time} and {second_event_time}")
                get_all_data_between_ons(all_data, first_event, second_event, filename)
        # print(f"Headset {hs_id} has {on_count} on_matches and {off_count} off_matches.")
    # print(f'In total there are {total_btb_ons} back_to_back on matches and {total_btb_offs} back-to-back off matches')

def remove_back_to_back_entries(headset_dict):
    for hs_id in headset_dict:
        events = headset_dict[hs_id]["events"]
        keys_to_remove = []
        i = 0
        while i < len(events) - 1:
            current_event = events[i]
            next_event = events[i + 1]
            if current_event["type"] == "on" and next_event["type"] == "on":
                # Find the oldest on match
                oldest_index = i
                while i < len(events) - 1 and events[i]["type"] == "on" and events[i + 1]["type"] == "on":
                    if events[i + 1]["timestamp"] < events[oldest_index]["timestamp"]:
                        oldest_index = i + 1
                    keys_to_remove.append(i + 1)
                    i += 1
                if oldest_index in keys_to_remove:
                    keys_to_remove.remove(oldest_index)  # Keep the oldest on match
            elif current_event["type"] == "off" and next_event["type"] == "off":
                # Find the youngest off match
                youngest_index = i
                while i < len(events) - 1 and events[i]["type"] == "off" and events[i + 1]["type"] == "off":
                    if events[i + 1]["timestamp"] > events[youngest_index]["timestamp"]:
                        youngest_index = i + 1
                    keys_to_remove.append(i)
                    i += 1
                keys_to_remove.append(i)  # Add the last checked off match
                if youngest_index in keys_to_remove:
                    keys_to_remove.remove(youngest_index)  # Keep the youngest off match
            i += 1
        for index in sorted(keys_to_remove, reverse=True):
            del events[index]

        # Update the 'on' and 'off' keys in headset_dict
        headset_dict[hs_id]["on"] = [event for event in events if event["type"] == "on"]
        headset_dict[hs_id]["off"] = [event for event in events if event["type"] == "off"]

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
def extract_false_awakenings(voice_data, criteria):
    # Sort the voice data by 'Headset ID'
    sorted_voice_data = sorted(voice_data, key=lambda x: x['Headset ID'])

    # Initialize the dictionary to store false awakenings count
    false_awakenings_data = {data['Headset ID']: 0 for data in sorted_voice_data if data['Headset ID'] != ""}

    # Count false awakenings
    for data in sorted_voice_data:
        if data['Headset ID'] != "":
            if data['Most Likely Outcome'] in criteria:
                false_awakenings_data[data['Headset ID']] += 1

    # Sort the false awakenings data by 'Headset ID'
    sorted_false_awakenings = dict(sorted(false_awakenings_data.items()))

    return sorted_false_awakenings

###gets the total uptime for each headset from the durations list
def get_total_uptime_per_headset(durations):
    headset_uptimes = {}

    for hs_id, times in durations.items():
        on_times = [entry["timestamp"] for entry in times["on"]]
        off_times = [entry["timestamp"] for entry in times["off"]]
        durations_list = []
        zipped = zip(on_times, off_times)
        for on_time, off_time in zipped:
            if off_time > on_time:  # Only subtract if off time is greater than on time
                duration = off_time - on_time
                durations_list.append(duration)
                # print(f'HS: {hs_id}, On time: {on_time}, Off time: {off_time}, Duration: {duration}')
        headset_uptimes[hs_id] = durations_list

    # Sum the durations for each headset and convert to seconds
    total_durations_seconds = {}

    for hs_id, durations_list in headset_uptimes.items():
        total_duration = sum(durations_list, timedelta())
        total_durations_seconds[hs_id] = total_duration.total_seconds()

    return total_durations_seconds

#################################################################

#############MAIN FUNCTIONS####################

###gets all headset data
###return all iterations of the data. From raw log lines ->  processed durations -> total uptimes
def get_hs_durations(m4_log_path, start_date, end_date):
    print("Getting Headset Log Lines as a list...")
    headset_on_off_raw_list, all_data = get_all_base_ext_headset_connected_duration(m4_log_path)
    print("Reformatting log lines to dictionaries...")
    durations_dict = process_data_set_for_duration(headset_on_off_raw_list, all_data, start_date, end_date)
    print("Calculating Uptimes per headset ID...")
    uptimes = get_total_uptime_per_headset(durations_dict)
    print("Headset Uptimes(Seconds): ")
    print(uptimes)

    # Convert seconds to hours
    uptimes_in_hours = {key: value / 3600 for key, value in uptimes.items()}
    print("Headset Uptimes(Hours): ")
    print(uptimes_in_hours)
    # Sum the uptimes in hours
    total_uptime_hours = sum(uptimes_in_hours.values())
    print(f"Total uptime in hours: {total_uptime_hours}")

    return headset_on_off_raw_list, durations_dict, uptimes_in_hours

def get_false_awakening_data_bound(path_to_ve_logs, start_date, end_date, selection, headsets, days, uptimes):
    if selection == 1:
        criteria = ["Timeout", "Other"]
    else:
        criteria = ["Reject", "Timeout", "Other", "Reject-User Not Notified", "Timeout-User Not Notified"]

    print("Getting Voice Engine Logs as a single string...")
    # Put voice engine log into a single string
    all_logs_in_str = get_all_voice_logs_as_str(path_to_ve_logs)

    print("Parsing String as list of voice sessions...")
    # Parse voice engine logs
    all_voice_sessions = parse_all_voice_logs_by_voice_session(all_logs_in_str)

    print("Processing Voice Data...")
    weekly_uptimes = {}
    all_voice_data = []

    # Convert start_date and end_date to datetime objects
    start_date = datetime.strptime(start_date, "%Y-%m-%d %H:%M:%S")
    end_date = datetime.strptime(end_date, "%Y-%m-%d %H:%M:%S")

    # Filter uptimes to include only selected headsets
    filtered_uptimes = {key: value for key, value in uptimes.items() if key in headsets}

    # Initialize the current start date for the first week
    current_start_date = start_date

    while current_start_date <= end_date:
        # Calculate the end date for the current week
        current_end_date = current_start_date + timedelta(days=6, hours=23, minutes=59, seconds=59)

        # Ensure the current end date does not exceed the overall end date
        if current_end_date > end_date:
            current_end_date = end_date

        print(f"Processing data from {current_start_date} to {current_end_date}...")

        voice_data = []

        for session in all_voice_sessions:
            # Extract the session date from the session data
            session_date_str = session[1][
                               1:18]  # Assuming the date is in the format 'MM/DD/YY HH:MM:SS' at the start of the session
            session_date = datetime.strptime(session_date_str, "%m/%d/%y %H:%M:%S")

            # Check if the session date is within the current week range
            if current_start_date <= session_date <= current_end_date:
                this_session_data = get_voice_session_data(session)

                if this_session_data is not None:
                    voice_data.append(this_session_data)
                    all_voice_data.append(this_session_data)

        print("Extracting False Awakenings...")
        false_awakening_data = extract_false_awakenings(voice_data, criteria)

        print("False Awakenings: ")
        for key, value in false_awakening_data.items():
            if key in headsets:  # Only process headsets in the specified list
                print(f'Headset ID: {key}, False Awakenings: {str(value)}')

                # Update the uptimes dictionary with false awakening data
                if (current_start_date, current_end_date) not in weekly_uptimes:
                    weekly_uptimes[(current_start_date, current_end_date)] = {}

                if key in filtered_uptimes:
                    # Check if the value in uptimes is already a dictionary
                    if isinstance(filtered_uptimes[key], dict):
                        weekly_uptimes[(current_start_date, current_end_date)][key] = {
                            'uptime': filtered_uptimes[key].get('uptime', 0),
                            'false_triggers': value
                        }
                    else:
                        weekly_uptimes[(current_start_date, current_end_date)][key] = {
                            'uptime': filtered_uptimes[key],
                            'false_triggers': value
                        }

        # Move to the next week
        current_start_date = current_end_date + timedelta(seconds=1)

    # Print the updated weekly uptimes dictionary
    for week, data in weekly_uptimes.items():
        print(f"Week {week}: {data}")

    return all_logs_in_str, all_voice_sessions, all_voice_data, false_awakening_data, weekly_uptimes


def get_rates(weekly_uptimes):
    rates = {}

    # Iterate over each week in the weekly_uptimes dictionary
    for week, data in weekly_uptimes.items():
        start_date, end_date = week

        # Calculate the false trigger rates for each headset
        for headset_id, value in data.items():
            if headset_id not in rates:
                rates[headset_id] = []

            if isinstance(value, dict) and value['uptime'] > 0:  # Ensure uptime is greater than 0 to avoid division by zero
                rate = (value['false_triggers'] / value['uptime']) * 100
                rates[headset_id].append({'week': (start_date, end_date), 'rate': rate})  # change so that "week" is actually a duration set by the user
            else:
                rates[headset_id].append({'week': (start_date, end_date), 'rate': None})

    # Print the entire rates dictionary before returning it
    print("\nComplete Rates Dictionary:")
    for headset_id, data in rates.items():
        print(f"Headset ID: {headset_id}")
        for entry in data:
            week_start, week_end = entry['week']
            rate = entry['rate']
            if rate is not None:
                print(f"  Week from {week_start.strftime('%Y-%m-%d')} to {week_end.strftime('%Y-%m-%d')}: {rate:.2f}%")
            else:
                print(f"  Week from {week_start.strftime('%Y-%m-%d')} to {week_end.strftime('%Y-%m-%d')}: N/A (Uptime is 0)")

    return rates

def plot_headset_data(rates):
    # Determine the common x-axis and y-axis limits
    all_weeks = []
    all_rates = []

    for data in rates.values():
        all_weeks.extend([f"{entry['week'][0].strftime('%Y-%m-%d')} to {entry['week'][1].strftime('%Y-%m-%d')}" for entry in data])
        all_rates.extend([entry['rate'] for entry in data if entry['rate'] is not None])

    # Get unique weeks and sort them
    unique_weeks = sorted(set(all_weeks))
    min_rate = min(all_rates)
    max_rate = max(all_rates)

    # Determine the number of subplots needed
    num_headsets = len(rates)
    num_cols = 2  # Number of columns for subplots
    num_rows = (num_headsets + num_cols - 1) // num_cols  # Calculate the number of rows needed

    # Create subplots
    fig, axes = plt.subplots(num_rows, num_cols, figsize=(15, num_rows * 5), squeeze=False)

    # Iterate over each headset in the rates dictionary
    for idx, (headset_id, data) in enumerate(rates.items()):
        row = idx // num_cols
        col = idx % num_cols
        ax = axes[row, col]

        weeks = [f"{entry['week'][0].strftime('%Y-%m-%d')} to {entry['week'][1].strftime('%Y-%m-%d')}" for entry in data]
        rates_values = [entry['rate'] for entry in data]

        # Plotting the data
        ax.plot(weeks, rates_values, label='False Trigger Rate (%)', marker='o')

        # Adding labels and title
        ax.set_xlabel('Week')
        ax.set_ylabel('False Trigger Rate (%)')
        ax.set_title(f'False Trigger Rate for Headset {headset_id} Over Time')
        ax.legend()
        ax.grid(True)

        # Set the same scale for all plots
        ax.set_ylim(min_rate, max_rate)
        ax.set_xticks(range(len(weeks)))
        ax.set_xticklabels(weeks, rotation=45)

    # Adjust layout to prevent overlap
    plt.tight_layout()
    plt.show()
    plt.pause(100)

if __name__ == '__main__':
    ##get headset on off list
    m4_log_path = 'C:/Users/mmarks/MykahFiles/Projects/FalseAwakenings/SYSTEM/logs/enc/m4/'
    path_to_ve_logs = 'C:/Users/mmarks/MykahFiles/Projects/FalseAwakenings/SYSTEM/logs/enc/voice_engine/'



    # start_date = "2024-10-11 11:50:00"
    start_date = "2024-11-1 00:00:00"
    # end_date = "2024-10-23 11:30:00"
    end_date = "2024-12-16 23:59:59"

    print("M4 Log Path: " + m4_log_path)
    print("Voice Engine Log Path: " + path_to_ve_logs)

    ##process headset durations
    print("--------------------PROCESSING HEADSET DATA-------------------")
    raw_list, durations_dict, uptimes = get_hs_durations(m4_log_path, start_date, end_date)


    ##get voice data
    print("--------------------PROCESSING VOICE DATA-------------------")
    selection = input("\nEnter 1 for non-inclusive search criteria, 2 for inclusive search criteria (regarding Most Likely Outcome categories)")
    headsets = input("Enter each headset ID you wish to view separated by a space: ").split()
    date_scale = input("How many days at a time would you like to look at? Enter as a number: ")
    voice_logs_as_str, all_voice_sessions_list, voice_data_dict, false_awakening_data, weekly_uptimes_with_false_triggers = get_false_awakening_data_bound(path_to_ve_logs, start_date, end_date, selection, headsets, date_scale, uptimes)

    rates = get_rates(weekly_uptimes_with_false_triggers)
    plot_headset_data(rates)

    