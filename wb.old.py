import json
import os

class WorkbenchError(Exception):
    """Exception raised when a notebook file cannot be found"""
    pass

meta_properties = {
    "name": "name",
    "folder": "properties.folder.name",
    "nbformat": "properties.nbformat",
    "nbformat_minor": "properties.nbformat_minor",
    "language": "properties.metadata.language_info.name"
}

def to_abs_path(path): 
    return os.path.abspath(os.path.join(os.getcwd(), path))

def get_property_by_path(o, path): 
    path_parts = path.split('.')
    value = o
    for part in path_parts: 
        if type(value) not in [dict]:
            return None
        if part not in value: 
            return None
        value = value[part]


    if type(value) not in [int, float, str]: 
        return None

    return value

def value_str(value) -> str: 
    if type(value) is str:
        return '"' + value.replace('\\', '\\\\').replace('"', '\\"') + '"'

    return str(value)

def parse_value(value_str): 
    if value_str.startswith('"') and value_str.endswith('"'): 
        return value_str.strip('"').replace('"', '\\"').replace('\\\\', '\\')
    try: 
        return int(value_str)
    except:
        pass

    try: 
        return float(value_str)
    except: 
        pass

    return None

def set_property_value(obj, path, value): 
    path_parts = path.split('.')
    
    dict_sect = obj

    for part in path_parts[0:-1]: 
        if type(dict_sect) != dict: 
            dict_sect[part] = {}

        dict_sect = dict_sect[part]

    dict_sect[path_parts[-1]] = value
    
def push_notebook(location, src): 
    """
    Push notebook from location to src
    Args:
        location: Source text file path
        src: Destination notebook file path
    """
    # Get current working directory and resolve relative paths
    cwd = os.getcwd()
    location = to_abs_path(location)
    src =  to_abs_path(src)
    
    # Ensure source file exists
    if not os.path.exists(location):
        raise WorkbenchError(f"File not found '{location}'")
    
    with open(location, 'r', encoding='utf-8') as source_file:
        content = source_file.read()
    
    # Read existing notebook to preserve metadata
    with open(src, 'r', encoding='utf-8') as notebook_file:
        notebook_data = json.load(notebook_file)
    
    # This is going to be the new cell data to write to the file
    new_cells = []
    
    # Parse the content
    current_cell = None
    
    for line in content.split('\n'):
        if line.startswith('@'):
            directive = line[1:line.find(' ')].lower()

            if directive == 'cell':     
                # Start new cell
                cell_def = line[6:].strip()  # Remove @CELL prefix
                cell_type = cell_def.split()[0]  # Get cell type
                
                # Check for tags
                tags = []
                if '[' in cell_def:
                    tag_part = cell_def[cell_def.find('['):cell_def.find(']')+1]
                    tags = [t.strip() for t in tag_part[1:-1].split(',') if t.strip()]
                
                # Create new cell
                current_cell = {
                    "cell_type": cell_type
                }
                # Only add metadata if there are tags
                if tags:
                    current_cell["metadata"] = {"tags": tags}
                
                current_cell["source"] = []
                current_cell["execution_count"] = 0

                new_cells.append(current_cell)

            if directive == 'meta': 
                sp1 = line.find(' ')
                sp2 = line.find(' ', sp1 + 1)

                prop_name = line[sp1+1:sp2]
                prop_value = line[sp2+1:]

                parsed_value = parse_value(prop_value)

                prop_path = meta_properties.get(prop_name, None)

                if prop_path is not None:
                    set_property_value(notebook_data, prop_path, parsed_value)


            if directive in ['cell', 'meta']: 
                continue

        if current_cell is not None:
            # Add line with newline, we'll clean up extra newlines at the end
            current_cell["source"].append(line + '\n')
    
    # Clean up extra newlines at the end of each cell
    for cell in new_cells:
        # Remove trailing newlines first
        while cell["source"] and cell["source"][-1].isspace():
            cell["source"].pop()
    
    notebook_data['properties']['cells'] = new_cells

    # Write the notebook file back to the same path we successfully read from
    os.remove(src)
    with open(src, 'w', newline="\n", encoding="utf-8") as dest_file:
        json.dump(notebook_data, dest_file, indent="\t")

def pull_notebook(location, src):
    """
    Pull notebook from location to src
    Args:
        location: Destination text file path
        src: Source notebook file path
    """
    src = to_abs_path(src)
    if not os.path.exists(src): 
        raise WorkbenchError(f"File not found '{src}'")
        
    location = to_abs_path(location)

    with open(src, 'r', encoding='utf-8') as source_file:
        file_data = json.load(source_file)

    dest_txt = ""

    for prop_name,prop_path in meta_properties.items(): 
        prop_value = get_property_by_path(file_data, prop_path)
        if prop_value is None: 
            continue
        prop_value_str = value_str(prop_value)
        if prop_value_str is None: 
            continue
        dest_txt += f"@meta {prop_name} {prop_value_str}\n"
    
    for cell in file_data["properties"]["cells"]:
        cell_txt = f"@cell {cell['cell_type']}"
        tags = cell.get("metadata", {}).get("tags", [])
        if len(tags) > 0: 
            cell_txt += f" [{','.join(tags)}]"
        cell_txt += "\n"
        cell_txt += "".join([line.rstrip("\n") + "\n" for line in cell['source']])
        dest_txt += cell_txt + "\n\n"
    
    with open(location, 'w', newline="\n", encoding="utf-8") as dest_file:
        dest_file.write(dest_txt)

def main():
    import sys
    
    if len(sys.argv) != 4:
        print("Usage: python wb.py <command> <location> <src>")
        print("Commands: push, pull")
        sys.exit(1)
    
    command = sys.argv[1].lower()
    location = sys.argv[2]
    src = sys.argv[3]
    
    try:

        if command == "push":
            push_notebook(location, src)
        elif command == "pull":
            pull_notebook(location, src)
        else:
            print(f"Unknown command: {command}")
            print("Available commands: push, pull")
            sys.exit(1)
    except WorkbenchError as wbe:
        print(wbe)
        sys.exit(1) 


if __name__ == '__main__': 
    main()
