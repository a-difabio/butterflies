import os
import numpy as np
import glob
from skimage import io, transform
from tqdm import tqdm
import math
import random
import torch
from torch.utils.data import DataLoader, Dataset
import multiprocessing
from config import *
import traceback
import webp

OUTPUT_RESOLUTION = 128
ROTATE = True

OUTPUT_DIRECTORY = 'data/images{:s}_{:d}/'.format('_rotated' if ROTATE else '', OUTPUT_RESOLUTION)

ERROR_WHILE_LOADING = -1

class ImageDataset(Dataset):
    def __init__(self, file_names):
        self.hashes = [f.split('/')[-1][:-5] for f in file_names]
        
    def __len__(self):
        return len(self.hashes)

    def __getitem__(self, index):
        hash = self.hashes[index]
        
        try:
            image = webp.imread('data/images_alpha/{:s}.webp'.format(hash)).astype(np.float32) / 255
            alpha_mask = image[:, :, 3][:, :, np.newaxis]
            image = image[:, :, :3] * alpha_mask  + (1 - alpha_mask)

            image = transform.resize(image[:, :, :3], (ROTATION_NETWORK_RESOLUTION, ROTATION_NETWORK_RESOLUTION), preserve_range=True)
            image = torch.tensor(image.transpose((2, 0, 1)), dtype=torch.float32)
        except:
            print("Error while loading {:s}".format(hash))
            return ERROR_WHILE_LOADING

        return image, hash    

def clip_image(image):
    WHITE_THRESHOLD = 0.95
    coords = ((image[:, :, 0] < WHITE_THRESHOLD) | (image[:, :, 1] < WHITE_THRESHOLD) | (image[:, :, 2] < WHITE_THRESHOLD)).nonzero()
    top_left = np.min(coords, axis=1)
    bottom_right = np.max(coords, axis=1)
    image = image[top_left[0]:bottom_right[0], top_left[1]:bottom_right[1], :]
    new_size = np.max(bottom_right - top_left)
    result = np.ones((new_size, new_size, 3), dtype=np.float32)
    x, y = (new_size - image.shape[0]) // 2, (new_size - image.shape[1]) // 2
    result[x:x+image.shape[0], y:y+image.shape[1], :] = image
    return result

def get_result_file_name(hash):
    return OUTPUT_DIRECTORY + '{:s}.jpg'.format(hash)

def handle_image(hash, angle):
    try:
        image = webp.imread('data/images_alpha/{:s}.webp'.format(hash)).astype(np.float32) / 255
        alpha_mask = image[:, :, 3][:, :, np.newaxis]
        image = image[:, :, :3] * alpha_mask  + (1 - alpha_mask)

        if angle is not None:
            image = transform.rotate(image, angle, resize=True, clip=True, mode='constant', cval=1)
            image = clip_image(image) * 255

        image = transform.resize(image, (OUTPUT_RESOLUTION, OUTPUT_RESOLUTION), preserve_range=True).astype(np.uint8)
        io.imsave(get_result_file_name(hash), image, quality=98)
    except:
        print("Error while handling {:s}".format(hash))
        traceback.print_exc()

if __name__ == '__main__':
    os.makedirs(OUTPUT_DIRECTORY, exist_ok=True)

    if ROTATE:
        from rotation_network import RotationNetwork
        device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        NETWORK_FILENAME = 'trained_models/rotation.to'
        network = RotationNetwork()
        network.load_state_dict(torch.load(NETWORK_FILENAME))
        network.cuda()
        network.eval()

        rotation_file = open(ROTATIONS_CALCULATED_FILENAME, 'a')

    file_names = glob.glob('data/images_alpha/**.webp', recursive=True)

    worker_count = os.cpu_count()
    print("Using {:d} processes.".format(worker_count))
    context = multiprocessing.get_context('spawn')
    pool = context.Pool(worker_count)

    progress = tqdm(total=len(file_names))

    def on_complete(*_):
        progress.update()

    if ROTATE:
        dataset = ImageDataset(file_names)        
        data_loader = DataLoader(dataset, batch_size=1, shuffle=True, num_workers=8)
        with torch.no_grad():
            for item in data_loader:
                if item == ERROR_WHILE_LOADING:
                    progress.update()
                    continue
                image, hashes = item
                hash = hashes[0]

                if os.path.exists(get_result_file_name(hash)):
                    progress.update()
                    continue

                result = network(image.to(device)).squeeze()
                angle = -math.degrees(math.atan2(result[0], result[1]))
                rotation_file.write('{:s},{:f}\n'.format(hash, angle))
                rotation_file.flush()

                pool.apply_async(handle_image, args=(hash, angle), callback=on_complete)
    else:
        random.shuffle(file_names)
        for file_name in file_names:
            hash = file_name.split('/')[-1][:-4]
            
            if os.path.exists(get_result_file_name(hash)):
                progress.update()
                continue

            pool.apply_async(handle_image, args=(hash, None), callback=on_complete)

    pool.close()
    pool.join()