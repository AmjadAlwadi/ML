import config
import time
import random
import os
import pickle
import torch

from transformers import AutoModelForCausalLM
from easyeditor import BaseEditor
from torch.utils.data import Dataset
from datasets import load_dataset
from sentence_transformers import SentenceTransformer
from sentence_transformers import util as st_util
from utils import log, create_response


        
def edit(edit_args, tokenizer):    
        
    editing_start_time = time.perf_counter()
    
    metrics = None
    edited_model = None
    
    if config.editing_method == "R-ROME":
        from easyeditor import ZsreDataset, R_ROMEHyperParams
        train_ds = ZsreDataset('./data/zsre/zsre_mend_train.json',size=10000)
        edit_args["train_ds"] = train_ds
        hparams = R_ROMEHyperParams.from_hparams(config.hparams_path)
        editor = BaseEditor.from_hparams(hparams)
        metrics, edited_model, _ = editor.edit(**edit_args)
    

    elif config.editing_method == "ROME":
        from easyeditor import ROMEHyperParams
        hparams = ROMEHyperParams.from_hparams(config.hparams_path)
        editor = BaseEditor.from_hparams(hparams)
        metrics, edited_model, _ = editor.edit(**edit_args)
    
    
    
    elif config.editing_method == "WISE":
        from easyeditor import WISEHyperParams
        hparams = WISEHyperParams.from_hparams(config.hparams_path)
        editor = BaseEditor.from_hparams(hparams)
        metrics, edited_model, _ = editor.edit(**edit_args)
        
    
    
    elif config.editing_method == "MEMIT":
        from easyeditor import MEMITHyperParams
        hparams = MEMITHyperParams.from_hparams(config.hparams_path)
        editor = BaseEditor.from_hparams(hparams)
        metrics, edited_model, _ = editor.edit(**edit_args)
        
        
        
        
    elif config.editing_method == "EMMET":
        from easyeditor import EMMETHyperParams
        hparams = EMMETHyperParams.from_hparams(config.hparams_path)
        editor = BaseEditor.from_hparams(hparams)
        metrics, edited_model, _ = editor.edit(**edit_args)
        
        
        
        
    elif config.editing_method == "PMET":
        from easyeditor import PMETHyperParams
        hparams = PMETHyperParams.from_hparams(config.hparams_path)
        editor = BaseEditor.from_hparams(hparams)
        metrics, edited_model, _ = editor.edit(**edit_args)
        
        
        
        
    elif config.editing_method == "MELO":
        from easyeditor import MELOHyperParams
        hparams = MELOHyperParams.from_hparams(config.hparams_path)
        editor = BaseEditor.from_hparams(hparams)
        metrics, edited_model, _ = editor.edit(**edit_args)
        
        
        
        
    elif config.editing_method == "GRACE":
        from easyeditor import GraceHyperParams
        hparams = GraceHyperParams.from_hparams(config.hparams_path)
        editor = BaseEditor.from_hparams(hparams)
        metrics, edited_model, _ = editor.edit(**edit_args)
        
        
        
        
    elif config.editing_method == "DPO":
        from easyeditor import DPOHyperParams
        hparams = DPOHyperParams.from_hparams(config.hparams_path)
        editor = BaseEditor.from_hparams(hparams)
        metrics, edited_model, _ = editor.edit(**edit_args)
        
        
        
    # Require pretraining      
    
    elif config.editing_method == "MEND":
        
        if config.train:
            from easyeditor import MENDTrainingHparams,EditTrainer,ZsreDataset
            training_hparams = MENDTrainingHparams.from_hparams(config.train_hparams_path)
            train_ds = ZsreDataset('./data/zsre/zsre_mend_train.json', config=training_hparams)
            eval_ds = ZsreDataset('./data/zsre/zsre_mend_eval.json', config=training_hparams)
            
            trainer = EditTrainer(
                config=training_hparams,
                train_set=train_ds,
                val_set=eval_ds,
            )
            
            trainer.run()
            
        else:
            from easyeditor import MENDHyperParams
            hparams = MENDHyperParams.from_hparams(config.hparams_path)
            editor = BaseEditor.from_hparams(hparams)
            metrics, edited_model, _ = editor.edit(**edit_args)
    
    
    
    
    elif config.editing_method == "SERAC":
        
        if config.train:
            from easyeditor import SERACTrainingHparams,EditTrainer,ZsreDataset
            training_hparams = SERACTrainingHparams.from_hparams(config.train_hparams_path)
            train_ds = ZsreDataset('./data/zsre/zsre_mend_train.json', config=training_hparams)
            eval_ds = ZsreDataset('./data/zsre/zsre_mend_eval.json', config=training_hparams)
            
            trainer = EditTrainer(
                config=training_hparams,
                train_set=train_ds,
                val_set=eval_ds,
            )
            trainer.run()
            
        else:
            from easyeditor import SERACHparams
            hparams = SERACHparams.from_hparams(config.hparams_path)
            editor = BaseEditor.from_hparams(hparams)
            metrics, edited_model, _ = editor.edit(**edit_args)
        
        
        
        
    elif config.editing_method == "MALMEN":
        
        if config.train:
            from easyeditor import SERACTrainingHparams,EditTrainer,ZsreDataset
            training_hparams = SERACTrainingHparams.from_hparams(config.train_hparams_path)
            train_ds = ZsreDataset('./data/zsre/zsre_mend_train.json', config=training_hparams)
            eval_ds = ZsreDataset('./data/zsre/zsre_mend_eval.json', config=training_hparams)
            
            trainer = EditTrainer(
                config=training_hparams,
                train_set=train_ds,
                val_set=eval_ds,
            )
            trainer.run()
            
        else:
            from easyeditor import SERACHparams
            hparams = SERACHparams.from_hparams(config.hparams_path)
            editor = BaseEditor.from_hparams(hparams)
            metrics, edited_model, _ = editor.edit(**edit_args)
            
               
               
                  
    elif config.editing_method == "IKE":
        if config.train:
            encode_ike_facts()
            
        
           
        
    elif config.editing_method == "FT-L" or config.editing_method == "FT-M":
        from easyeditor import FTHyperParams
        hparams = FTHyperParams.from_hparams(config.hparams_path)
        editor = BaseEditor.from_hparams(hparams)
        metrics, edited_model, _ = editor.edit(**edit_args)
        
        
        
        
    elif config.editing_method == "LORA":
        from easyeditor import LoRAHyperParams
        hparams = LoRAHyperParams.from_hparams(config.hparams_path) 
        editor = BaseEditor.from_hparams(hparams)
        metrics, edited_model, _ = editor.edit(**edit_args)
        
        
        
    elif config.editing_method == "INSTRUCTION_ENGINEERING":
        
        model = AutoModelForCausalLM.from_pretrained(config.model_name,torch_dtype=config.weights_dtype, token=config.access_token,device_map='auto')
        log("Loaded base model",True,False,True)
        
        # Apparently best template
        #"Judge the correctness of every action by simply saying either moral or immoral! and Imagine that " + prompts[0] + " moral"
        
        messages = [
            {
                "role": "system",
                "content": "Imagine that " + edit_args["prompts"][0] + " " + edit_args["target_new"][0],
            },
            
            {"role": "user", "content": edit_args["prompts"][0]},
        ]
        
        create_response(model,tokenizer,messages,instructinoal=True)
            
        return
    

    
    # This does nothing excpept for a semantic search on the training dataset for 
    # similar prompts and does not even return those found examples.
    
    # elif editing_method == "IKEs":
    #     from easyeditor import IKEHyperParams
    #     from easyeditor import CounterFactDataset
        
    #     hparams = IKEHyperParams.from_hparams(hparams_path)
    #     train_ds = CounterFactDataset('./data/counterfact/counterfact-train.json')
        
    #     if train:
    #         from easyeditor.models.ike import encode_ike_facts
    #         from sentence_transformers import SentenceTransformer
    #         sentence_model = SentenceTransformer(hparams.sentence_model_name).to(f'cuda:{hparams.device}')
    #         encode_ike_facts(sentence_model, train_ds, hparams)
            
        # else:
        #     editor = BaseEditor.from_hparams(hparams)
        #     metrics, edited_model, sentence = editor.edit(
        #         prompts=prompts,
        #         ground_truth=ground_truth,
        #         target_new=target_new,
        #         train_ds=train_ds,
        #         locality_inputs=locality_inputs,
        #     )
    
        #     edited_model = pre_edit_model
    

    
    
    else:
        from sys import exit
        log(f"Invalid editing method: {config.editing_method}",False,True,True)
        exit(1)
          
        
    editing_end_time = time.perf_counter()
    
    return metrics, edited_model, editing_end_time - editing_start_time











def construct_ike_template(new_fact, target_new, prompt = None, ground_truth = None):
    # Copy template
    if not prompt and not ground_truth:
        return f"New Fact: {new_fact} {target_new}\nPrompt: {new_fact} {target_new}\n\n"  
    # Update template
    elif not ground_truth:
        return f"New Fact: {new_fact} {target_new}\nPrompt: {prompt} {target_new}\n\n"
    # Retain template
    else:
        return f"New Fact: {new_fact} {target_new}\nPrompt: {prompt} {ground_truth}\n\n"







def generate_random_list():
    '''
    Construct a list with the desired length and with occurrences that match the probabilities given
    
    '''
    
    count_0 = int(config.ike_demos_number * config.ike_copy_probability)  # 12.5% for 0
    count_1 = int(config.ike_demos_number * config.ike_update_probability)  # 37.5% for 1
    count_2 = config.ike_demos_number - count_0 - count_1  # Remaining for 2 (50%)

    random_list = [2] * count_2 + [1] * count_1 + [0] * count_0

    # Shuffle the list to randomize the order
    # Order of demos in IKE has negligible effect
    random.shuffle(random_list)

    return random_list






def create_ike_template(ike_dataset):
    
    template = ""
    case_numbers = generate_random_list()
    
    ike_loc_dataset_index = 0
    
    # Construct the demonstration examples
    for j in range(0, config.ike_demos_number):
        
        new_fact = ike_dataset['prompt'][j]
        target_new = ike_dataset['target_new'][j]
        prompt = None
        ground_truth = None
        
        # Generate a random number with the specified probabilities
        case_number = case_numbers[j]        
        
        if case_number == 0:
            prompt = None
            ground_truth = None
        elif case_number == 1:
            prompt = ike_dataset['strong_rephrase_prompt'][j]
            ground_truth = target_new
        else:
            prompt = ike_dataset['prompt'][ike_loc_dataset_index + config.ike_demos_number]
            ground_truth = ike_dataset['ground_truth'][ike_loc_dataset_index + config.ike_demos_number]
            ike_loc_dataset_index += 1
            
        template += construct_ike_template(new_fact, target_new, prompt, ground_truth)
    
    # log(f"Demonstrations Length is {len(template.split(' '))}", True, True, True)
    
    # print()
    # log(template, True, True, True)
    # print()
    
    
    
    return template








# def create_ike_prompts(edit_args):
    
#     results = []
    
#     for i in range(len(edit_args["prompts"])):
        
#         result = ""
        
#         # Add the new fact
#         result += construct_ike_template(edit_args["prompts"][i], edit_args["target_new"][i])

#         # Add paraphrses
#         # Add only the second paraphrase because the remainings are in question form
#         result += construct_ike_template(edit_args["light_rephrase_prompts"][i][1], edit_args["target_new"][i])
#         # result += construct_ike_template(edit_args["light_rephrase_prompts"][i][0], edit_args["target_new"][i])
#         # result += construct_ike_template(edit_args["light_rephrase_prompts"][i][2], edit_args["target_new"][i]) 
#         # result += construct_ike_template(edit_args["portability_inputs"]["synonym"]["prompt"][i], edit_args["portability_inputs"]["synonym"]["ground_truth"][i])
#         result += construct_ike_template(edit_args["strong_rephrase_prompts"][i], edit_args["target_new"][i])
        
#         # Add locality prompts and only the neighborhood without distracting
#         for j in range(i * (config.ike_demos_number + 1), (i * (config.ike_demos_number + 1)) + config.ike_demos_number):
#             result += construct_ike_template(edit_args["locality_inputs"]["neighborhood"]["prompt"][j], edit_args["locality_inputs"]["neighborhood"]["ground_truth"][j])
        
#         print(f"Old length was {len(edit_args['prompts'][i].split(' '))} and new length is {len(result.split(' '))}")
#         print()
#         log(result, True, True, True)
#         print()
        
#         results.append(result)
    
#     return results







def encode_ike_facts():
    sentence_model = SentenceTransformer(config.sentence_model_name).to(config.device)

    ds_path = f"{config.datasets_path}/norms/edit_norms_datasets/edit_norms_dataset.json"
    ds = load_dataset("json", data_files = ds_path, split='train')
    
    sentences = []
    half_size = (len(ds)//2)
    
    for i in range(len(ds)):
        new_fact = ds[i]['prompt'] + ' ' + ds[i]['target_new']
        target_new = ds[i]['target_new']
        
        if i >= half_size:
            loc_neighbor_ground_truth = ds[i - half_size]['ground_truth']
            neighbor = ds[i - half_size]['prompt']
            sentences.append(f"New Fact: {new_fact}\nPrompt: {neighbor} {loc_neighbor_ground_truth}\n\n")
        else:
            sentences.append(f"New Fact: {new_fact}\nPrompt: {new_fact}\n\n")
            
            paraphrases = ds[i]['strong_rephrase_prompt']
            sentences.append(f"New Fact: {new_fact}\nPrompt: {paraphrases} {target_new}\n\n")
            
        

    embeddings = sentence_model.encode(sentences)
    base_path = f'{config.results_dir}/{config.editing_method}/embedding'
    os.makedirs(base_path, exist_ok=True)
    safe_model_name = config.sentence_model_name.rsplit('/', 1)[-1]
    with open(f'{base_path}/{safe_model_name}_{type(ds).__name__}_11779.pkl', "wb") as fOut:
        pickle.dump({'sentences': sentences, 'embeddings': embeddings}, fOut,
                    protocol=pickle.HIGHEST_PROTOCOL)
        







def find_examples(edit_args):

    prompt = edit_args["prompts"][0]
    target_new = edit_args["target_new"][0]
    
    sentence_model = SentenceTransformer(config.sentence_model_name).to(config.device)

    safe_model_name = config.sentence_model_name.rsplit('/', 1)[-1]
    with open(f'{config.results_dir}/{config.editing_method}/embedding/'
              f'{safe_model_name}_Dataset_11779.pkl', "rb") as fIn:
        stored_data = pickle.load(fIn)
        stored_sentences = stored_data['sentences']
        stored_embeddings = stored_data['embeddings']
    stored_embeddings = torch.tensor(stored_embeddings).to(config.device)
    stored_embeddings = st_util.normalize_embeddings(stored_embeddings)

    new_fact = prompt + ' ' + target_new
    query_sentence = f"New Fact: {new_fact}\nPrompt: {prompt}\n\n"
    query_embedding = st_util.normalize_embeddings(torch.tensor(sentence_model.encode(
        query_sentence, show_progress_bar=False)).unsqueeze(0).to(config.device))

    hits = st_util.semantic_search(query_embedding, stored_embeddings, score_function=st_util.dot_score, top_k=config.ike_demos_number)
    assert len(hits) == 1
    hit = hits[0]
    icl_examples = [stored_sentences[hit[k]["corpus_id"]] for k in range(len(hit))]
    icl_examples.append(f'New Fact: {new_fact}\nPrompt: {new_fact}\n\n')
    
    log('The found examples are:', True, False, False)
    for ex in icl_examples:
        log(ex, True, False, False)
    
    return "".join(icl_examples)