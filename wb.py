import json
import os
from typing import Optional
from abc import ABC, abstractmethod

class WorkbenchError(Exception):
    """Exception raised when a notebook file cannot be found"""
    pass
    
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

class NotebookCellData:
    def __init__(self, cell_type: str, contents: str,  attributes: list[str]):
        self.cell_type = cell_type
        self.contents = contents
        self.attributes = attributes

class NotebookData: 
    def __init__(self, name: str, properties: dict, cells: list[NotebookCellData]): 
        self.name = name
        self.properties = properties
        self.cells = cells

class NotebookFormat(ABC): 
    @abstractmethod
    def read_file(self, src_path: str) -> NotebookData:
        pass

    @abstractmethod
    def write_file(self, dest_path: str, nb_data: NotebookData): 
        pass 


class SynapseNotebookFormat(NotebookFormat):
    meta_properties = {
        "folder": "folder.name",
        "nbformat": "nbformat",
        "nbformat_minor": "nbformat_minor",
        "language": "metadata.language_info.name"
    }


    def read_file(self, src_path: str) -> NotebookData:
        with open(src_path, 'r', encoding="utf-8") as file: 
            file_data = json.load(file)

        name = file_data.get('name')
        properties = {}
        properties_obj = file_data.get('properties')
        cells = []

        for prop_name,prop_path in self.meta_properties.items(): 
            prop_value = get_property_by_path(properties_obj, prop_path)
            properties[prop_name] = prop_value

        for cell_data in properties_obj.get('cells'):
            tags = cell_data.get('metadata', {}).get('tags', [])
            cell_type = cell_data.get("cell_type")
            cell_content = "".join([line.rstrip("\n") + "\n" for line in cell_data['source']])
            cell_obj = NotebookCellData(cell_type, cell_content, tags)
            cells.append(cell_obj)
        
        return NotebookData(name, properties, cells)

    def write_file(self, dest_path: str, nb_data: NotebookData):
        if os.path.exists(dest_path): 
            with open(dest_path, 'r', encoding='utf-8') as dest_file: 
                file_data = json.load(dest_file)
        else: 
            file_data = _get_detault_notebook_data()

        set_property_value(file_data, 'name', nb_data.name)

        properties = file_data.get('properties', {})

        for prop_name, prop_value in nb_data.properties.items(): 
            if prop_path := self.meta_properties.get(prop_name, None): 
                set_property_value(properties, prop_path, prop_value)
        
        cells = []

        for cell in nb_data.cells: 
            cell_content_lines = [f"{line}\n" for line in cell.contents.rstrip(" \n\t\r").split("\n")]
            cell_data = {
                "cell_type": cell.cell_type,
                "source": cell_content_lines
            }

            if len(cell.attributes) > 0: 
                cell_data["tags"] = cell.attributes

            cell_data["execution_count"] = 0

            cells.append(cell_data)
        
        set_property_value(properties, 'cells', cells)

        set_property_value(file_data, 'properties', properties)

        with open(dest_path, 'w', newline='\n', encoding='utf-8') as dest_file: 
            json.dump(file_data, dest_file, indent="\t")


    def _get_default_notebook_data() -> str: 
        script_dir = os.path.dirname(os.path.abspath(__file__))
        read_text_file(f"{script_dir}/nb_default.json")


class ScratchpadNotebookFormat(NotebookFormat): 
    def read_file(self, src_path) -> NotebookData: 
        with open(src_path, 'r') as src_file: 
            file_content = src_file.read()

        name = ""
        properties = {}
        cells = []

        current_cell = None

        for line in file_content.split('\n'): 
            if line.startswith('@'): 
                directive = line[1:line.find(' ')].lower()
                
                if directive == 'cell': 
                    cell_def = line[6:].strip() # Remove @cell prefix
                    cell_type = cell_def.split(' ')[0] # Get cell type

                    tags = []
                    if '[' in cell_def: 
                        tag_part = cell_def[cell_def.find('['):cell_def.find(']')+1]
                        tags = [t.strip() for t in tag_part[1: -1].split(',') if t.strip()]

                    current_cell = NotebookCellData(cell_type, "", tags)

                    cells.append(current_cell)

                    continue
                    
                if directive == 'meta': 
                    sp1 = line.find(' ')
                    sp2 = line.find(' ', sp1 + 1)

                    prop_name = line[sp1+1:sp2]
                    prop_value = line[sp2+1:]

                    parsed_value = parse_value(prop_value)

                    if prop_name == 'name': 
                        name = parsed_value
                    else: 
                        properties[prop_name] = parsed_value

                    continue

            if current_cell is not None: 
                current_cell.contents += line + '\n'

        return NotebookData(name, properties, cells)

    def write_file(self, dest_path: str, nb_data: NotebookData): 
        new_file_text = ""
        
        new_file_text += f"@meta name {value_str(nb_data.name)}\n"
        
        for prop_name, prop_value in nb_data.properties.items():
            new_file_text += f"@meta {prop_name} {value_str(prop_value)}\n"

        for cell in nb_data.cells:
            attribute_str = ""
            if len(cell.attributes): 
                attribute_list = ','.join(cell.attributes)
                attribute_str = f" [{attribute_list}]"

            new_file_text += f"@cell {cell.cell_type}{attribute_str}\n{cell.contents}\n"

        with open(dest_path, 'w', newline='\n', encoding='utf-8') as dest_file:
            dest_file.write(new_file_text)

local_format = ScratchpadNotebookFormat()
remote_format = SynapseNotebookFormat()


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
    src = to_abs_path(src)
    
    # Ensure source file exists
    if not os.path.exists(location):
        raise WorkbenchError(f"File not found '{location}'")
    
    nb_data = local_format.read_file(location)
    remote_format.write_file(src, nb_data)

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

    nb_data = remote_format.read_file(src)
    local_format.write_file(location, nb_data)

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
