import json

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

    for line in lines:
        line = line.strip()
        if not line:  # Skip empty lines or lines with only spaces
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

# Example OpenFOAM-like input string
openfoam_input = """
engineType turbojet;
airProperties
{
    temperature 223;
    pressure 26400;
    density 0.413;
}
components
{
    intake
    {
        Phi 1;
        mach 0.8;
        efficiency 0.97;
    }
    compressor
    {
        pressure_ratio 15.0;
        efficiency 0.88;
        mechanical_efficiency 0.98;
    }
    combustor
    {
        outlet_temperature 1450;
        efficiency 0.99;
        mechanical_efficiency 0.95;
    }
    turbine
    {
        efficiency 0.92;
        mechanical_efficiency 0.98;
    }
    nozzle
    {
        efficiency 0.97;
    }
}
"""

# Parse the OpenFOAM-like input into a dictionary
config_dict = parse_openfoam_style(openfoam_input)

# Save the dictionary to JSON file
json_file = 'config.json'
save_to_json(config_dict, json_file)

print(f"Converted OpenFOAM-like input to JSON: {json_file}")
