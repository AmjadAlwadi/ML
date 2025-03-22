import datasets
from datasets import load_dataset, Dataset, concatenate_datasets
from transformers.pipelines.pt_utils import KeyDataset
from transformers import pipeline
import torch
import tqdm
import argparse
import time
import numpy as np
import os

from coherence.generate_morally_coherent_norms_1 import filter_moral_batch, filter_immoral_batch, load_edit_norms
from coherence.generate_morally_coherent_norms_2 import is_textually_neutral, remove_most_falses_first, remove_non_neutral_norms, create_classifier_input_dataset

datasets_path = "../datasets"


def count_files_in_directory(directory_path):
    """Returns the number of files in the given directory."""
    if not os.path.isdir(directory_path):
        # raise ValueError(f"Invalid directory: {directory_path}")
        return 0
    
    return sum(1 for item in os.listdir(directory_path) if os.path.isfile(os.path.join(directory_path, item)))




if __name__ == '__main__':
    global entailment_threshold, contradiction_threshold, batch_size
    
    device = torch.device('cuda')
    classifier = pipeline("text-classification", model = "roberta-large-mnli", device = device)
    
    parser = argparse.ArgumentParser(description='Filter norms dataset based so that the moral_action/immoral_action entails/contradicts the rot_action.')
    parser.add_argument('-s','--subset_size', type=int, default=100, help='Size of the subset to process, -1 for full dataset')
    parser.add_argument('-b', '--batch_size', type=int, default=20, help='Batch size for processing')
    parser.add_argument('-e','--entailment_threshold', type=float, default=0.75, help='Minimum score for entailment')
    parser.add_argument('-c','--contradiction_threshold', type=float, default=0.85, help='Minimum score for contradiction')
    parser.add_argument('-t','--tolerance_range', type=float, default=0.32, help='Maximum score allowed for contradiction. If lower than 0.32 then contradiction is not allowed. Disabled at default')
    parser.add_argument('--shuffle', action='store_true', help='Shuffle the dataset')
    
    args = parser.parse_args()
    
    
    # try without the judgment it is better
    # write the old method and new method in paper
    
    
    subset_size = args.subset_size
    entailment_threshold = args.entailment_threshold
    contradiction_threshold = args.contradiction_threshold
    tolerance_range = args.tolerance_range
    batch_size = args.batch_size
    shuffle = args.shuffle
    
    
    edit_norms_subset = load_edit_norms(subset_size, shuffle)
    
    start_time_1 = time.time()
    result = edit_norms_subset.filter(lambda batch: filter_moral_batch(batch, classifier, entailment_threshold, batch_size), batched=True, batch_size=batch_size)
    result = edit_norms_subset.filter(lambda batch: filter_immoral_batch(batch, classifier, contradiction_threshold, batch_size), batched=True, batch_size=batch_size)
    end_time_1 = time.time()
    
    
    print(f"Generating coherent norms 1 took {end_time_1 - start_time_1:.2f} seconds.")
    print(f"Number of neutral items: {len(result)}")
    
    start_time_2 = time.time()
    input_dataset, index_map = create_classifier_input_dataset(edit_norms_subset)
    neutrality_matrix = is_textually_neutral(input_dataset, index_map, batch_size, tolerance_range, classifier, subset_size)
    neutral_elements = remove_most_falses_first(neutrality_matrix)
    result = edit_norms_subset.filter(lambda row, index: remove_non_neutral_norms(row, index, neutral_elements), with_indices=True)
    end_time_2 = time.time()
    
    print(f"Generating coherent norms 2 took {end_time_2 - start_time_2:.2f} seconds.")
    print(f"Number of neutral items: {len(result)}")
    
    if '__index_level_0__' in result.column_names:    
        result = result.remove_columns(['__index_level_0__'])
        
    path = f"{datasets_path}/norms/coherent_edit_norms_datasets"
    number_of_files = count_files_in_directory(path)
    
    print(f"Saved dataset in {datasets_path}")
    result.to_json(f"{path}/E{entailment_threshold}_C{contradiction_threshold}_T{tolerance_range}_S{subset_size}_N{len(result)}_{number_of_files + 1}.json")
    
    
