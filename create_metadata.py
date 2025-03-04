from tqdm import tqdm
import csv
from config import *

class DataProperty():
    def __init__(self, column, name, type=str):
        self.column = column
        self.name = name
        self.values = []
        self.type = type

columns = [
    DataProperty(31, 'Family'),
    DataProperty(34, 'Genus'),
    DataProperty(60, 'Species'),
    # DataProperty(31, 'Subspecies'),
    DataProperty(35, 'Higher Classification'),
    DataProperty(59, 'Sex'),
    DataProperty(25, 'Latitude', float),
    DataProperty(26, 'Longitude', float),
    DataProperty(22, 'Country'),
    # DataProperty(59, 'Name'),
    # DataProperty(60, 'Name Author'),
    # DataProperty(9, 'Day'),
    # DataProperty(50, 'Month'),
    DataProperty(69, 'Year'),
    DataProperty(0, 'id', int),
    DataProperty(47, 'Occurence ID'),
]

file = open('data/resource.csv', 'r')
reader = csv.reader(file)
reader_iterator = iter(reader)
column_names = next(reader_iterator)

row_by_id = {}

row_index = 0
progress = tqdm(total=8557, desc='Reading resource.csv')

image_ids = []

for row in reader_iterator:
    id = int(row[0])
    progress.update()
    if 'lepidoptera' not in row[49].lower():
            continue
    for data_property in columns:
        data_property.values.append(row[data_property.column].strip())

    row_by_id[id] = row_index
    row_index += 1

    image = row[6].split(' | ')[0]
    title = row[11].split(' | ')[0]
    if 'label' in title:
        continue
    # if row[3] != 'image/jpeg':
    #     continue
    # if id not in row_by_id:
    #     continue
    image_ids.append((image, id))

with open(METADATA_FILE_NAME, 'w') as file:
    csv_writer = csv.writer(file, delimiter=',')
    csv_writer.writerow([c.name for c in columns] + ['image'])
    for image, id in tqdm(image_ids, desc='Writing metadata.csv'):
        row_index = row_by_id[id]
        csv_writer.writerow([c.values[row_index] for c in columns] + [image])