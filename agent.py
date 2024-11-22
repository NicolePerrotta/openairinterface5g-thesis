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
            # Look for the throughput format in the log file (e.g., "1.05 Mbits/sec")
            match = re.search(r"([\d\.]+)\s(Kbits/sec|Mbits/sec|Gbits/sec)", line)
            if match:
                # Extract the throughput value and convert it to Mbps
                value = float(match.group(1))
                unit = match.group(2)
                if unit == "Kbits/sec":
                    throughput = value / 1000  # Convert Kbits to Mbits
                elif unit == "Mbits/sec":
                    throughput = value
                elif unit == "Gbits/sec":
                    throughput = value * 1000  # Convert Gbits to Mbits
                break
        else:
            # If no throughput information is found, continue to the next iteration
            time.sleep(1)
            continue

        # Acquire the lock to safely read the threshold
        with threshold_lock:
            current_threshold = threshold

        # Read the JSON file
        with open(output_file, 'r') as f:
            data = json.load(f)

        # Get the "max_ratio" value from the first entry
        max_ratio = data["rrmPolicyRatio"][0]["max_ratio"]

        # Adjust the max_ratio based on the throughput
        if throughput > current_threshold:
            # Reduce by 5% (clamped between 0 and 100)
            new_max_ratio = max(0, min(100, max_ratio * 0.95))
            change_message = (
                f"Detected throughput: {throughput:.4f} Mbps\n"
                f"Throughput above threshold. max_ratio decreased from {max_ratio} to {new_max_ratio}.\n"
            )
        else:
            # Increase by 5% (clamped between 0 and 100)
            new_max_ratio = max(0, min(100, max_ratio * 1.05))
            change_message = (
                f"Detected throughput: {throughput:.4f} Mbps\n"
                f"Throughput below threshold. max_ratio increased from {max_ratio} to {new_max_ratio}.\n"
            )

        # Save the change message to the changes file
        with open(changes_file, 'a') as changes_log:
            changes_log.write(change_message)

        # Update the value in the JSON
        data["rrmPolicyRatio"][0]["max_ratio"] = new_max_ratio

        # Write the updated JSON back to the file
        with open(output_file, 'w') as f:
            json.dump(data, f, indent=4)

        time.sleep(1)


def update_threshold():
    """Thread to update the threshold value based on user input."""
    global threshold
    while True:
        try:
            # Prompt the user for a new threshold value
            new_threshold = float(input("\nEnter a new throughput threshold (in Mbps): "))
            
            # Safely update the global threshold
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
        # Clear the changes file at the start of the program
        with open(changes_file, 'w') as f:
            f.write("")  # Overwrite the file with an empty string

        # Initialize the threshold
        threshold = float(input("Enter the initial throughput threshold (in Mbps): "))

        # Start the threshold update thread
        threshold_thread = threading.Thread(target=update_threshold, daemon=True)
        threshold_thread.start()

        # Start monitoring throughput
        monitor_throughput()
    except KeyboardInterrupt:
        print("\nExiting program.")
