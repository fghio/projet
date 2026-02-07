import json
import importlib
import os

from src.write.exerciseText import generate_exercise_text, generate_data_section

def parse_value(value):
    try:
        # Attempt to convert the value to a float, then to an int if applicable
        float_value = float(value)
        if float_value.is_integer():
            return int(float_value)
        return float_value
    except ValueError:
        # If conversion fails, return the value as is (string)
        return value

def parse_openfoam_style(openfoam_string):
    lines = openfoam_string.strip().splitlines()
    config_dict = {}
    stack = []
    current_dict = config_dict
    current_key = None

    header_skipped = False


    for line in lines:
        line = line.strip()
        if not line:  # Skip empty lines or lines with only spaces
            continue
        
        # Skip lines until the 'engineType' keyword is found
        if not header_skipped:
            if 'engineType' in line:
                header_skipped = True
            else:
                continue

        # Skip comment lines
        if line.startswith('//'):
            continue

        if line.endswith('{'):
            key = line[:-1].strip()
            new_dict = {}
            if current_key:
                current_dict[current_key] = new_dict
            else:
                current_dict[key] = new_dict
            stack.append((current_dict, current_key))
            current_dict = new_dict
            current_key = None
        elif line == '}':
            current_dict, current_key = stack.pop()
        else:
            key_value = line.rstrip(';').split(maxsplit=1)
            if len(key_value) == 2:
                key, value = key_value
                current_dict[key] = parse_value(value)
            else:
                current_key = key_value[0]

    return config_dict


def save_to_json(config_dict, json_file):
    with open(json_file, 'w') as f:
        json.dump(config_dict, f, indent=2)


def load_config(config_file):
    with open(config_file, 'r') as f:
        config = json.load(f)
    return config


# run the corresponding engine type
def run_engine(config):
    engine_type = config['engineType']
    engine_module = importlib.import_module(f"applications.engines.{engine_type}")
    engine_module.simulate(config)


if __name__ == "__main__":
    # Print current directory for debugging purposes
    print(f"Current directory: {os.getcwd()}")

    # Ensure the input file exists
    input_file_path = 'input'  # Update this path if necessary
    if not os.path.isfile(input_file_path):
        print(f"Error: The file '{input_file_path}' does not exist.")
    else:
        with open(input_file_path, 'r') as f:
            inputFile = f.read()

        # Parse the OpenFOAM-like input into a dictionary
        config_dict = parse_openfoam_style(inputFile)

        # Save the dictionary to JSON file (to be sure)
        save_to_json(config_dict, 'config.json')

        config_file = 'config.json'
        config = load_config(config_file)
        run_engine(config)

        exercise_text = generate_exercise_text(config)
        print(exercise_text)
        exercise_data = generate_data_section(config)
        print(exercise_data)

