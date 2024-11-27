import threading
import json
import time
import re

# File paths
output_file = 'rrmPolicy.json'
iperf_log_file = '/oai-ran/iperf_server.txt'
changes_file = 'changes.txt'

# Global variable for threshold
threshold = 0.0
threshold_lock = threading.Lock()  # Lock to manage concurrent access to the threshold

def monitor_throughput():
    """Monitor throughput and adjust max_ratio."""
    global threshold
    while True:
        with open(iperf_log_file, 'r') as log_file:
            lines = log_file.readlines()

        # Process the log file from the most recent entries
        for line in reversed(lines):
            match = re.search(r"([\d\.]+)\s(Kbits/sec|Mbits/sec|Gbits/sec)", line)
            if match:
                value = float(match.group(1))
                unit = match.group(2)
                throughput = value / 1000 if unit == "Kbits/sec" else value * 1000 if unit == "Gbits/sec" else value
                break
        else:
            time.sleep(1)
            continue

        with threshold_lock:
            current_threshold = threshold

        with open(output_file, 'r') as f:
            data = json.load(f)

        changes = []
        percentage = 0.02
        for policy in data["rrmPolicyRatio"]:
            max_ratio = policy["max_ratio"]
            set_mcs = policy["set_mcs"]
            if throughput > (1+percentage)*current_threshold:
                new_max_ratio = max(2, min(100, max_ratio - 2))
                change_message = (
                    f"Throughput: {throughput:.4f} Mbps => max_ratio decreased from {max_ratio} to {new_max_ratio}"
                )
                if new_max_ratio==2 and set_mcs>4:
                    policy["set_mcs"] = set_mcs-1
                    f"and mcs decreased of 1"
                f".\n"
            elif throughput < (1-percentage)*current_threshold:
                policy["set_mcs"] = 0
                new_max_ratio = max(2, min(100, max_ratio + 2)) 
                change_message = (
                    f"Throughput: {throughput:.4f} Mbps => max_ratio increased from {max_ratio} to {new_max_ratio}.\n"
                )
            else:
                f"Throughput: {throughput:.4f} Mbps around the threshold.\n"
            if new_max_ratio != max_ratio:
                changes.append(change_message)
                policy["max_ratio"] = new_max_ratio

        with open(changes_file, 'a') as changes_log:
            changes_log.writelines(changes)

        with open(output_file, 'w') as f:
            json.dump(data, f, indent=4)

        time.sleep(1)

def update_threshold():
    """Thread to update the threshold value based on user input."""
    global threshold
    while True:
        try:
            new_threshold = float(input("\nEnter a new throughput threshold (in Mbps): "))
            with threshold_lock:
                threshold = new_threshold
                print(f"Threshold updated to {threshold} Mbps.")
        except ValueError:
            print("Invalid input. Please enter a numeric value.")
        except KeyboardInterrupt:
            print("\nExiting program.")
            break

if __name__ == "__main__":
    try:
        with open(changes_file, 'w') as f:
            f.write("")

        threshold = float(input("Enter the initial throughput threshold (in Mbps): "))

        threshold_thread = threading.Thread(target=update_threshold, daemon=True)
        threshold_thread.start()

        monitor_throughput()
    except KeyboardInterrupt:
        print("\nExiting program.")
