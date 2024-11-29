import datasets
from datasets import load_dataset, Dataset, concatenate_datasets
from transformers.pipelines.pt_utils import KeyDataset
from transformers import pipeline
import torch
import tqdm
import argparse


def load_norms():
    global norms_subset
    norms = load_dataset("datasets/norms/", data_files="norms_dataset.json", split='train')
    n = len(norms) if subset_size == -1 else subset_size
    norms_subset = norms.select(range(n))




def is_textually_entailed_batch(texts, hypotheses):
    inputs = [f"{text.rstrip('.?')}. {hypothesis.rstrip('.?')}." for text, hypothesis in zip(texts, hypotheses)]
    results = classifier(inputs, batch_size=batch_size)
    entailments = [
        result['label'] == 'ENTAILMENT' and result['score'] >= entailment_threshold
        for result in results
    ]
    return entailments



def is_textually_contradicted_batch(texts, hypotheses):
    inputs = [f"{text.rstrip('.?')}. {hypothesis.rstrip('.?')}." for text, hypothesis in zip(texts, hypotheses)]
    results = classifier(inputs, batch_size=batch_size)
    contradictions = [
        result['label'] == 'CONTRADICTION' and result['score'] >= contradiction_threshold
        for result in results
    ]
    return contradictions





def filter_moral_batch(batch):
    moral_actions = batch['moral_action']
    rot_actions = batch['rot_action']
    entailments = is_textually_entailed_batch(moral_actions, rot_actions)
    return entailments






def filter_immoral_batch(batch):
    immoral_actions = batch['immoral_action']
    rot_actions = batch['rot_action']
    contradictions = is_textually_contradicted_batch(immoral_actions, rot_actions)
    return contradictions





if __name__ == '__main__':
    global subset_size, entailment_threshold, contradiction_threshold, batch_size
    
    device = torch.device('cuda')
    classifier = pipeline("text-classification", model = "roberta-large-mnli", device = device)
    
    parser = argparse.ArgumentParser(description='Filter norms dataset based on textual entailment and contradiction.')
    parser.add_argument('-s','--subset_size', type=int, default=-1, help='Size of the subset to process')
    parser.add_argument('-e','--entailment_threshold', type=float, default=0.75, help='Minimum score for entailment')
    parser.add_argument('-c','--contradiction_threshold', type=float, default=0.85, help='Minimum score for contradiction')
    parser.add_argument('-b', '--batch_size', type=int, default=2000, help='Batch size for processing')
    
    args = parser.parse_args()
    
    subset_size = args.subset_size
    entailment_threshold = args.entailment_threshold
    contradiction_threshold = args.contradiction_threshold
    batch_size = args.batch_size
    
    load_norms()

    result = norms_subset.filter(filter_moral_batch, batched=True, batch_size=batch_size)
    result = norms_subset.filter(filter_immoral_batch, batched=True, batch_size=batch_size)
    
    # Save it only if the full dataset was selected
    if subset_size == -1:
        result.to_json(f"datasets/norms/norms_dataset_e{entailment_threshold}_c{contradiction_threshold}.json")
    
    print(len(result))