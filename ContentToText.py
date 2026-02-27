import os

data_path = "Data"
all_content = open(f"{data_path}/AllContent.txt", "w")
files = os.listdir(data_path)

def dump_content_to_text(directory : str):
    if os.path.isdir(directory):
        for item in os.listdir(directory):
            if item.endswith(".json"):
                with open(directory + "/" + item, "r") as f:
                    data = f.read()
                    all_content.write("File: " + item + "\n")
                    all_content.write(data + "\n\n")
            else:
                dump_content_to_text(directory + "/" + item)

for directory in files:
    if os.path.isdir(data_path + "/" + directory):
        print(f"Dumping content from {directory}...")
        dump_content_to_text(data_path + "/" + directory)

all_content.close()
print(f"All content has been dumped to {data_path}/AllContent.txt")