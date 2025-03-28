import torch
import config
import time
import random
import os
import tqdm

from transformers import pipeline
from datasets import load_dataset
from colorama import Fore, Back, Style, init
from utils import create_response, append_to_metadata, log, write_output_to_file, common_prefix, count_tokens, find_file_by_ending_number
from dataset_creation.rephrases.utils import send_request
from edit import create_ike_template, find_examples


def load_norms():
    
    full_dataset_path = f"{config.datasets_path}/norms/edit_norms_datasets/edit_norms_dataset.json"
    full_dataset = load_dataset("json", data_files = full_dataset_path, split='train')
    
    if config.shuffle:
        seed = int(time.time()) ^ random.randint(0, 2**32 - 1)  # XOR for added randomness
        full_dataset = full_dataset.shuffle(seed=seed)
    
    ds = full_dataset.select(range(config.norms_subset_size))
    coherent_dataset_name = find_file_by_ending_number(f"{config.datasets_path}/norms/coherent_edit_norms_datasets/", config.norms_dataset_number)

    if coherent_dataset_name and config.norms_dataset_number != 0:
        coherent_dataset_path = f"{config.datasets_path}/norms/coherent_edit_norms_datasets/{coherent_dataset_name}"
        coherent_dataset = load_dataset("json", data_files = coherent_dataset_path, split='train')
        ds = coherent_dataset.select(range(config.norms_subset_size))
        
    elif not coherent_dataset_name and config.norms_dataset_number != 0:
        log(f"No dataset found for number {config.norms_dataset_number}.",True, True, True)
        return

    config.norms_subset_size =  min(config.norms_subset_size, len(full_dataset) // 2)
    
    loc_dataset_size = config.norms_subset_size
    locality_dataset = full_dataset.select(range(config.norms_subset_size, config.norms_subset_size + loc_dataset_size))
    ike_demonstrations_dataset = None
    
    if config.editing_method == "IKE":
        
        ike_loc_dataset_size = config.ike_demos_number - int(config.ike_demos_number * config.ike_copy_probability) - int(config.ike_demos_number * config.ike_update_probability) 
        
        if config.norms_subset_size + loc_dataset_size + config.ike_demos_number + ike_loc_dataset_size > len(full_dataset):
            log("loc examples number is too big.",True, True, True)
            return
        else:
            ike_demonstrations_dataset = full_dataset.select(range(config.norms_subset_size + loc_dataset_size, config.norms_subset_size + loc_dataset_size + config.ike_demos_number + ike_loc_dataset_size))
    
    
    
    prompts = ds['prompt']
    ground_truth = ds['ground_truth']
    target_new = ds['target_new']
    action_moral_judgment = ds["action_moral_judgment"]
    
    subject = ds['subject']
    light_rephrase_prompts = ds['light_rephrase_prompts']
    strong_rephrase_prompts = ds['strong_rephrase_prompt']
    prompt_subject = ds['prompt_subject']
    
    moral_action = ds["moral_action"]
    immoral_action = ds["immoral_action"]
    situation = ds["situation"]
    
    
    locality_inputs_neighborhood_prompt = locality_dataset["prompt"]
    locality_inputs_neighborhood_ground_truth = locality_dataset["ground_truth"]
    locality_inputs_action_moral_judgement = locality_dataset["action_moral_judgment"]
    
    locality_inputs_distracting_prompt = [f"{prompts[i]} {target_new[i]}. {locality_inputs_neighborhood_prompt[i]}" for i in range(len(ds))]
    locality_inputs_distracting_ground_truth = locality_dataset["ground_truth"]

    portability_inputs_one_hop_prompt = [f"{sit} {mor}" for sit, mor in zip(situation, moral_action)]
    portability_inputs_two_hop_prompt = [f"{sit} {immor}" for sit, immor in zip(situation, immoral_action)]
    
    # Needed for WISE
    loc_prompts = [f"{pr} {tn}" for pr, tn in zip(locality_inputs_neighborhood_prompt, locality_inputs_neighborhood_ground_truth)]

    locality_inputs = {}
    portability_inputs = {}
    
    locality_inputs = {
        "neighborhood":{
            "prompt": locality_inputs_neighborhood_prompt,
            "ground_truth": locality_inputs_neighborhood_ground_truth
        },
        "distracting":{
            "prompt": locality_inputs_distracting_prompt,
            "ground_truth": locality_inputs_distracting_ground_truth
        }
	}         

             
    portability_inputs = {
        "synonym":{
            "prompt": prompt_subject,
            "ground_truth":target_new
        },
      
        "one_hop":{
            "prompt": portability_inputs_one_hop_prompt,
            "ground_truth": target_new
        },
        
        "two_hop":{
            "prompt": portability_inputs_two_hop_prompt,
            "ground_truth": ground_truth
        }
    }         

        
    log("Norms dataset loaded",False,False,True)
    
    norms_dict = {
        "prompts": prompts,
        "ground_truth": ground_truth,
        "target_new": target_new,
        "subject": subject,
        "light_rephrase_prompts": light_rephrase_prompts,
        "strong_rephrase_prompts": strong_rephrase_prompts,
        "locality_inputs": locality_inputs,
        "locality_inputs_action_moral_judgement": locality_inputs_action_moral_judgement,
        "portability_inputs": portability_inputs,
        "action_moral_judgment": action_moral_judgment,
        "moral_action": moral_action,
        "immoral_action": immoral_action, 
        "loc_prompts": loc_prompts
    }
    

    

    # Alternatives
    # 'The action "Earning income to support your family" is best described by a single adjective:'
    # 'Earning income to support your family is morally'
    # 'Earning income to support your family is best described as:'
    # 'The action "Starting fires in a park" is best described by a single adjective:'
    


    return norms_dict, ike_demonstrations_dataset








def output_token_scores(tokenizer, scores, batch_element_index):
    
    # Get top 10 tokens and their probabilities
    score_output = ""
    top_tokens = []
    for score in scores:
        # Apply softmax to get probabilities
        probs = torch.nn.functional.softmax(score, dim=-1)
        # Get the top 10 tokens
        top_k_probs, top_k_ids = torch.topk(probs, config.scores_top_k, dim=-1)
        top_tokens.append((top_k_ids, top_k_probs))


    col1_width = 30
    col2_width = 30
    
    # Decode tokens to strings and print
    for i, (ids, probs) in enumerate(top_tokens):
        score_output += f"Token {i + 1}:\n"
        print(Fore.LIGHTMAGENTA_EX + f"Token {i + 1}:" + Style.RESET_ALL)
        
        for token, prob in zip(ids[batch_element_index], probs[batch_element_index]):
            
            decoded_token = tokenizer.decode(token)
            
            if decoded_token == "\n":
                decoded_token = "newline"
            elif decoded_token == "\n\n":
                decoded_token = "double_newline"        
                
            score_output += f"{decoded_token:<{col1_width}}| {prob.item():<{col2_width}}\n"    
            print(f"{decoded_token:<{col1_width}}| " + Fore.RED + f"{prob.item():<{col2_width}}" + Style.RESET_ALL)
        
        score_output += "\n"
        print()
        
    return score_output









def calculate_kl_divergence_for_token(pre_edit_logits, post_edit_logits, element_index, token_index):
    
    """
    Calculates the KL divergence for a single token at the specified index.
    
    element_index is the index of the element within the batch
    
    Returns the KL divergence and if a batch is given then the batchmean will be calculated.
    
    """
    
    # Pick the specified token
    pre_edit_logit = pre_edit_logits[token_index]
    post_edit_logit = post_edit_logits[token_index]
    
    # Pick the specified element/row but if beam search then average the result of all beams
    pre_edit_logit = pre_edit_logit[element_index].unsqueeze(dim=0)
    post_edit_logit = post_edit_logit[element_index].unsqueeze(dim=0)
        
    # Move to same device
    pre_edit_logit = pre_edit_logit.to(post_edit_logit.device)
    
    # Convert logits to probabilities
    original_probs = torch.nn.functional.softmax(pre_edit_logit, dim=-1)
    edited_probs = torch.nn.functional.softmax(post_edit_logit, dim=-1)

    # Compute KL divergence
    kl_divergence = torch.nn.functional.kl_div(original_probs.log(), edited_probs, reduction='batchmean', log_target=False)

    return kl_divergence












def calculate_batch_kl_divergence_for_token(pre_edit_logits, post_edit_logits, token_index):
    
    """
    Calculates the KL divergence for a single token at the specified index.
    
    Returns the KL divergence and if a batch is given then the batchmean will be calculated.
    
    """
    
    # Pick the specified token
    pre_edit_logit = pre_edit_logits[token_index]
    post_edit_logit = post_edit_logits[token_index]
    
    # Move to same device
    pre_edit_logit = pre_edit_logit.to(post_edit_logit.device)
    
    # Convert logits to probabilities
    original_probs = torch.nn.functional.softmax(pre_edit_logit, dim=-1)
    edited_probs = torch.nn.functional.softmax(post_edit_logit, dim=-1)

    # Compute KL divergence
    kl_divergence = torch.nn.functional.kl_div(original_probs.log(), edited_probs, reduction='batchmean')

    return kl_divergence







def construct_prompt_engineering_edit_args(tokenizer, edit_args, ike_demonstrations_dataset):
    if config.editing_method == "IKE":
        return construct_ike_edit_args(tokenizer, edit_args, ike_demonstrations_dataset)
    elif config.editing_method == "ICE":
        return construct_ice_edit_args(tokenizer, edit_args)
    else:
        return None



def construct_ike_edit_args(tokenizer, edit_args, ike_demonstrations_dataset):
    
    def format_ike_new_fact(new_fact, target_new):
        return f'New Fact: {new_fact} {target_new}\n'
          
          
          
    def format_ike_prompt(prompt):
        return f'Prompt: {prompt}'
        
    
    
    def format_ike_full_prompt(ike_template, edit_args):
        
        result = ike_template
        
        for i in range(len(edit_args["prompts"])):
            result += format_ike_new_fact(edit_args["prompts"][i], edit_args["target_new"][i])
        
        return result
    
    
        
    ike_template = ""
    
    if config.ike_demos_number != 0:
    
        if config.ike_selection_mechanism == "similarity" and config.norms_subset_size == 1:
            ike_template = find_examples(edit_args)
        else:
            ike_template = create_ike_template(ike_demonstrations_dataset)
            
    ike_template = format_ike_full_prompt(ike_template, edit_args) # For sequential editing
    append_to_metadata({"ike_template_size": count_tokens(tokenizer, ike_template)})
    
    # log(ike_template, True, False, False)
    
    ike_edit_args = {
        "prompts": [ike_template +  format_ike_prompt(edit_args["prompts"][i]) for i in range(len(edit_args["prompts"]))],  
        "ground_truth": edit_args["ground_truth"],
        "target_new": edit_args["target_new"],
        "subject": edit_args["subject"],
        "locality_inputs":{
            
            "neighborhood":{
                "prompt": [ike_template + format_ike_prompt(edit_args["locality_inputs"]["neighborhood"]["prompt"][i]) for i in range(len(edit_args["prompts"]))],
                "ground_truth": edit_args["locality_inputs"]["neighborhood"]["ground_truth"]
            },
            "distracting":{
                "prompt": [ike_template + format_ike_prompt(edit_args["locality_inputs"]["distracting"]["prompt"][i]) for i in range(len(edit_args["prompts"]))],
                "ground_truth": edit_args["locality_inputs"]["distracting"]["ground_truth"]
            }
        },    
        
        "locality_inputs_action_moral_judgement" : edit_args["locality_inputs_action_moral_judgement"],
        "rephrase_prompts": format_ike_prompt(edit_args["strong_rephrase_prompts"]),
        "portability_inputs" : {
            
            "synonym":{
                "prompt": [ike_template + format_ike_prompt(edit_args["portability_inputs"]["synonym"]["prompt"][i]) for i in range(len(edit_args["prompts"]))],
                "ground_truth": edit_args["portability_inputs"]["synonym"]["ground_truth"]
            },
        
            "one_hop":{
                "prompt": [ike_template + format_ike_prompt(edit_args["portability_inputs"]["one_hop"]["prompt"][i]) for i in range(len(edit_args["prompts"]))],
                "ground_truth": edit_args["portability_inputs"]["one_hop"]["ground_truth"]
            },
            
            "two_hop":{
                "prompt": [ike_template + format_ike_prompt(edit_args["portability_inputs"]["two_hop"]["prompt"][i]) for i in range(len(edit_args["prompts"]))],
                "ground_truth": edit_args["portability_inputs"]["two_hop"]["ground_truth"]
            }
        },
        
        "action_moral_judgment": edit_args["action_moral_judgment"],
        "light_rephrase_prompts": [ [ike_template + format_ike_prompt(edit_args["light_rephrase_prompts"][i][0]),
                                    ike_template + format_ike_prompt(edit_args["light_rephrase_prompts"][i][1]),
                                    ike_template + format_ike_prompt(edit_args["light_rephrase_prompts"][i][2])] 
                                for i in range(len(edit_args["light_rephrase_prompts"]))],
        
        "strong_rephrase_prompts": [ike_template + format_ike_prompt(edit_args["strong_rephrase_prompts"][i]) for i in range(len(edit_args["strong_rephrase_prompts"]))],
        
        # "loc_prompts" : edit_args["loc_prompts"],
        # "moral_action": edit_args["moral_action"],
        # "immoral_action": edit_args["immoral_action"],
        # "sequential_edit": True
    }

    return ike_edit_args







def construct_ice_edit_args(tokenizer, edit_args):
    
    def format_ice_new_fact(new_fact, target_new):
        return f'Imagine that {new_fact} {target_new}. '
        
          
          
    def format_ice_prompt(prompt):
        return f'{prompt}'
        
    
    def format_ice_full_prompt(edit_args):
        result = ""
        
        for i in range(len(edit_args["prompts"])):
            result += format_ice_new_fact(edit_args["prompts"][i], edit_args["target_new"][i])
        
        return result
    
    
          
    ice_template = format_ice_full_prompt(edit_args) # For sequential editing
    append_to_metadata({"ice_template_size": count_tokens(tokenizer, ice_template)})
    
    
    ice_edit_args = {
        "prompts": [ice_template +  format_ice_prompt(edit_args["prompts"][i]) for i in range(len(edit_args["prompts"]))],  
        "ground_truth": edit_args["ground_truth"],
        "target_new": edit_args["target_new"],
        "subject": edit_args["subject"],
        "locality_inputs":{
            
            "neighborhood":{
                "prompt": [ice_template + format_ice_prompt(edit_args["locality_inputs"]["neighborhood"]["prompt"][i]) for i in range(len(edit_args["prompts"]))],
                "ground_truth": edit_args["locality_inputs"]["neighborhood"]["ground_truth"]
            },
            "distracting":{
                "prompt": [ice_template + format_ice_prompt(edit_args["locality_inputs"]["distracting"]["prompt"][i]) for i in range(len(edit_args["prompts"]))],
                "ground_truth": edit_args["locality_inputs"]["distracting"]["ground_truth"]
            }
        },    
        
        "locality_inputs_action_moral_judgement" : edit_args["locality_inputs_action_moral_judgement"],
        "rephrase_prompts": [ice_template + format_ice_prompt(edit_args["strong_rephrase_prompts"][i]) for i in range(len(edit_args["strong_rephrase_prompts"]))],
        "portability_inputs" : {
            
            "synonym":{
                "prompt": [ice_template + format_ice_prompt(edit_args["portability_inputs"]["synonym"]["prompt"][i]) for i in range(len(edit_args["prompts"]))],
                "ground_truth": edit_args["portability_inputs"]["synonym"]["ground_truth"]
            },
        
            "one_hop":{
                "prompt": [ice_template + format_ice_prompt(edit_args["portability_inputs"]["one_hop"]["prompt"][i]) for i in range(len(edit_args["prompts"]))],
                "ground_truth": edit_args["portability_inputs"]["one_hop"]["ground_truth"]
            },
            
            "two_hop":{
                "prompt": [ice_template + format_ice_prompt(edit_args["portability_inputs"]["two_hop"]["prompt"][i]) for i in range(len(edit_args["prompts"]))],
                "ground_truth": edit_args["portability_inputs"]["two_hop"]["ground_truth"]
            }
        },
        
        "action_moral_judgment": edit_args["action_moral_judgment"],
        "light_rephrase_prompts": [ [ice_template + format_ice_prompt(edit_args["light_rephrase_prompts"][i][0]),
                                    ice_template + format_ice_prompt(edit_args["light_rephrase_prompts"][i][1]),
                                    ice_template + format_ice_prompt(edit_args["light_rephrase_prompts"][i][2])] 
                                for i in range(len(edit_args["light_rephrase_prompts"]))],
        
        "strong_rephrase_prompts": [ice_template + format_ice_prompt(edit_args["strong_rephrase_prompts"][i]) for i in range(len(edit_args["strong_rephrase_prompts"]))],
        
        # "loc_prompts" : edit_args["loc_prompts"],
        # "moral_action": edit_args["moral_action"],
        # "immoral_action": edit_args["immoral_action"],
        # "sequential_edit": True
    }

    return ice_edit_args









def preprare_responses(tokenizer, model, edit_args, ike_edit_args):
    
    if model is None:
        log("No model has been specified", True, True, True)
        return
    
    

    # Gets the generated part, strips unnecessary characters from the left and return the string till the period
    def format_output(outputs, length, index):
        
        results = []
        
        for i in range(config.num_return_sequences):
            
            output = outputs[config.num_return_sequences * index + i]
            result = output[length:]
            result = result.lstrip(" .,?\n")
            result = result.rstrip(" ,\n\"")
            p_index = result.find('.') 
            q_index = result.find('?')
            n_index = result.find('\n')
            
            if p_index != -1:
                result = f"{result[:p_index]}."
            elif q_index!= -1:
                result = f"{result[:q_index]}?"
            elif n_index!= -1:
                result = f"{result[:n_index]}."
            else:
                result = result
            
            results.append(result)
                
        return results    
    
    
    
    decoded_responses_prompt = []
        
    decoded_responses_light_rephrase_1 = []
    decoded_responses_light_rephrase_2 = []
    decoded_responses_light_rephrase_3 = []
    
    decoded_responses_strong_rephrase = []
    
    decoded_responses_portability_synonym = []
    decoded_responses_portability_one_hop = [] 
    decoded_responses_portability_two_hop = [] 

    decoded_responses_locality_neighborhood = []
    decoded_responses_locality_distracting = []
    
    decoded_unformatted_responses_locality_neighborhood = []
    decoded_unformatted_responses_locality_distracting = []

    logits = []
    scores = []

    used_edit_args = edit_args

    # If IKE and post edit, then use the new IKE prompts
    if ike_edit_args:
        used_edit_args = ike_edit_args
    
    
    
    for edit_index in tqdm.tqdm(range(config.norms_subset_size)):
        
        # To work all answers in parallel
        
        # We could do every type separately, but this will be effective for large batch sizes/number_of_edits > 10
        # We don't intend to go beyond 10 edits here, so it will be pointless to think about this kind of scaling
        # The reason is the limitations of current editing methods and the possessed hardware.
        # The other reason is that with beam search, the memory requirements grow exponentially against the number of beams, so it's not useful
        # to have batch sizes over 10
        
        model_input = [
            
            used_edit_args["prompts"][edit_index],
                   
            used_edit_args["light_rephrase_prompts"][edit_index][0],
            used_edit_args["light_rephrase_prompts"][edit_index][1],
            used_edit_args["light_rephrase_prompts"][edit_index][2],
            
            used_edit_args["strong_rephrase_prompts"][edit_index],
            
            used_edit_args["portability_inputs"]["synonym"]["prompt"][edit_index],
            used_edit_args["portability_inputs"]["one_hop"]["prompt"][edit_index],
            used_edit_args["portability_inputs"]["two_hop"]["prompt"][edit_index],
    
            used_edit_args["locality_inputs"]["neighborhood"]["prompt"][edit_index],
            used_edit_args["locality_inputs"]["distracting"]["prompt"][edit_index],

        ]
        
        
        # Lists to store outputs for this edit_index
        decoded_outputs = []
        logits_prompt = []
        scores_prompt = []
        final_logits_tuple, final_scores_tuple = None, None
        
        
        if config.batching:

            # Create responses then batch decode then reformat the outputs
            output = create_response(model,tokenizer,model_input,instructinoal=False)
            decoded_outputs = tokenizer.batch_decode(output.sequences,skip_special_tokens=True)
            final_logits_tuple = output.logits
            final_scores_tuple = output.scores
        
        else:
            
            # Process each prompt sequentially
            for prompt in model_input:
                model_input = [prompt]
                output = create_response(model, tokenizer, model_input, instructinoal=False)
                decoded_output = tokenizer.batch_decode(output.sequences, skip_special_tokens=True)
                decoded_outputs.extend(decoded_output)
                logits_prompt.append(output.logits)
                scores_prompt.append(output.scores)
            
            
            # Fix here, it doesn't work for beams = norms = 1 search for some reason
            
            # len(logits_prompt)
            
            # Reorganize logits_prompt into a list of max_new_tokens tensors, each with 10 elements
            reorganized_logits_tensors = list(zip(*logits_prompt)) 
            final_logits_tuple = tuple(torch.cat(tensors, dim=0) for tensors in reorganized_logits_tensors)
            
            if config.enable_output_scores:
                reorganized_scores_tensors = list(zip(*scores_prompt)) 
                final_scores_tuple = tuple(torch.cat(tensors, dim=0) for tensors in reorganized_scores_tensors)
            

        decoded_responses_prompt.append(format_output(decoded_outputs, len(used_edit_args["prompts"][edit_index]), 0))
        
        decoded_responses_light_rephrase_1.append(format_output(decoded_outputs, len(used_edit_args["light_rephrase_prompts"][edit_index][0]), 1))
        decoded_responses_light_rephrase_2.append(format_output(decoded_outputs, len(used_edit_args["light_rephrase_prompts"][edit_index][1]), 2))
        decoded_responses_light_rephrase_3.append(format_output(decoded_outputs, len(used_edit_args["light_rephrase_prompts"][edit_index][2]), 3))
        
        decoded_responses_strong_rephrase.append(format_output(decoded_outputs, len(used_edit_args["strong_rephrase_prompts"][edit_index]), 4)) 
        
        decoded_responses_portability_synonym.append(format_output(decoded_outputs, len(used_edit_args["portability_inputs"]["synonym"]["prompt"][edit_index]), 5)) 
        decoded_responses_portability_one_hop.append(format_output(decoded_outputs, len(used_edit_args["portability_inputs"]["one_hop"]["prompt"][edit_index]), 6)) 
        decoded_responses_portability_two_hop.append(format_output(decoded_outputs, len(used_edit_args["portability_inputs"]["two_hop"]["prompt"][edit_index]), 7))

        decoded_responses_locality_neighborhood.append(format_output(decoded_outputs, len(used_edit_args["locality_inputs"]["neighborhood"]["prompt"][edit_index]), 8)) 
        decoded_responses_locality_distracting.append(format_output(decoded_outputs, len(used_edit_args["locality_inputs"]["distracting"]["prompt"][edit_index]), 9)) 

        # Without removing any trailing spaces or commas etc. to use later for perplexity metric
        decoded_unformatted_responses_locality_neighborhood.append([decoded_outputs[idx] for idx in range(config.num_return_sequences * 8, config.num_return_sequences * 8 + config.num_return_sequences)]) 
        decoded_unformatted_responses_locality_distracting.append([decoded_outputs[idx] for idx in range(config.num_return_sequences * 9, config.num_return_sequences * 9 + config.num_return_sequences)]) 

    
        logits.append(final_logits_tuple)
        
        
        
        
        
        # print(decoded_outputs)
        # print(decoded_responses_prompt)
        
        # print(len(final_logits_tuple))       # 8
        # print(len(final_logits_tuple[0]))    # 10
        # print(len(final_logits_tuple[0][0])) # 1
        
        if config.enable_output_scores:
            scores.append(final_scores_tuple)
    

    return_dict = {
        "prompt": decoded_responses_prompt,
        "light_rephrase_1": decoded_responses_light_rephrase_1,
        "light_rephrase_2": decoded_responses_light_rephrase_2,
        "light_rephrase_3": decoded_responses_light_rephrase_3,
        "strong_rephrase": decoded_responses_strong_rephrase,
        "portability_synonym": decoded_responses_portability_synonym,
        "portability_one_hop": decoded_responses_portability_one_hop,
        "portability_two_hop": decoded_responses_portability_two_hop,
        "locality_neighborhood": decoded_responses_locality_neighborhood,
        "locality_distracting": decoded_responses_locality_distracting,
        "unformatted_locality_neighborhood": decoded_unformatted_responses_locality_neighborhood,
        "unformatted_locality_distracting":  decoded_unformatted_responses_locality_distracting 
    }
    
    # It took me an hour to come up with this
    # Basically, this returns the logits of each edit in the desired format
    # This iterates over all edit logits and combines all return sequences/beams of each type into one batch, then combines those into one tensor
    # This is done for every single token
    
    # Ask tomorrow
    # Tensors should be rectangular but max tokens is not always the case
    
    
    
    logits_dict = {
        "prompt": tuple(torch.cat(tuple(torch.cat([tup[i][0 * config.num_beams + idx] for idx in range(config.num_beams)],dim=0) for tup in logits),dim=0).reshape(config.num_beams * config.norms_subset_size, tokenizer.vocab_size) for i in range(config.max_new_tokens)),
        "light_rephrase_1": tuple(torch.cat(tuple(torch.cat([tup[i][1 * config.num_beams + idx] for idx in range(config.num_beams)],dim=0) for tup in logits),dim=0).reshape(config.num_beams * config.norms_subset_size,tokenizer.vocab_size) for i in range(config.max_new_tokens)),
        "light_rephrase_2": tuple(torch.cat(tuple(torch.cat([tup[i][2 * config.num_beams + idx] for idx in range(config.num_beams)],dim=0) for tup in logits),dim=0).reshape(config.num_beams * config.norms_subset_size, tokenizer.vocab_size) for i in range(config.max_new_tokens)),
        "light_rephrase_3": tuple(torch.cat(tuple(torch.cat([tup[i][3 * config.num_beams + idx] for idx in range(config.num_beams)],dim=0) for tup in logits),dim=0).reshape(config.num_beams * config.norms_subset_size, tokenizer.vocab_size) for i in range(config.max_new_tokens)),
        "strong_rephrase": tuple(torch.cat(tuple(torch.cat([tup[i][4 * config.num_beams + idx] for idx in range(config.num_beams)],dim=0) for tup in logits),dim=0).reshape(config.num_beams * config.norms_subset_size, tokenizer.vocab_size) for i in range(config.max_new_tokens)),
        "portability_synonym": tuple(torch.cat(tuple(torch.cat([tup[i][5 * config.num_beams + idx] for idx in range(config.num_beams)],dim=0) for tup in logits),dim=0).reshape(config.num_beams * config.norms_subset_size, tokenizer.vocab_size) for i in range(config.max_new_tokens)),
        "portability_one_hop": tuple(torch.cat(tuple(torch.cat([tup[i][6 * config.num_beams + idx] for idx in range(config.num_beams)],dim=0) for tup in logits),dim=0).reshape(config.num_beams * config.norms_subset_size, tokenizer.vocab_size) for i in range(config.max_new_tokens)),
        "portability_two_hop": tuple(torch.cat(tuple(torch.cat([tup[i][7 * config.num_beams + idx] for idx in range(config.num_beams)],dim=0) for tup in logits),dim=0).reshape(config.num_beams * config.norms_subset_size, tokenizer.vocab_size) for i in range(config.max_new_tokens)),
        "locality_neighborhood": tuple(torch.cat(tuple(torch.cat([tup[i][8 * config.num_beams + idx] for idx in range(config.num_beams)],dim=0) for tup in logits),dim=0).reshape(config.num_beams * config.norms_subset_size, tokenizer.vocab_size) for i in range(config.max_new_tokens)),
        "locality_distracting": tuple(torch.cat(tuple(torch.cat([tup[i][9 * config.num_beams + idx] for idx in range(config.num_beams)],dim=0) for tup in logits),dim=0).reshape(config.num_beams * config.norms_subset_size, tokenizer.vocab_size) for i in range(config.max_new_tokens)),
    }
    
    

    scores_dict = None
    if config.enable_output_scores:
    
        scores_dict = {
            "prompt": tuple(torch.cat(tuple(torch.cat([tup[i][0 * config.num_beams + idx] for idx in range(config.num_beams)],dim=0) for tup in scores),dim=0).reshape(config.num_beams * config.norms_subset_size, tokenizer.vocab_size) for i in range(config.max_new_tokens)),
            "light_rephrase_1": tuple(torch.cat(tuple(torch.cat([tup[i][0 * config.num_beams + idx] for idx in range(config.num_beams)],dim=0) for tup in scores),dim=0).reshape(config.num_beams * config.norms_subset_size, tokenizer.vocab_size) for i in range(config.max_new_tokens)),
            "light_rephrase_2": tuple(torch.cat(tuple(torch.cat([tup[i][0 * config.num_beams + idx] for idx in range(config.num_beams)],dim=0) for tup in scores),dim=0).reshape(config.num_beams * config.norms_subset_size, tokenizer.vocab_size) for i in range(config.max_new_tokens)),
            "light_rephrase_3": tuple(torch.cat(tuple(torch.cat([tup[i][0 * config.num_beams + idx] for idx in range(config.num_beams)],dim=0) for tup in scores),dim=0).reshape(config.num_beams * config.norms_subset_size, tokenizer.vocab_size) for i in range(config.max_new_tokens)),
            "strong_rephrase": tuple(torch.cat(tuple(torch.cat([tup[i][0 * config.num_beams + idx] for idx in range(config.num_beams)],dim=0) for tup in scores),dim=0).reshape(config.num_beams * config.norms_subset_size, tokenizer.vocab_size) for i in range(config.max_new_tokens)),
            "portability_synonym": tuple(torch.cat(tuple(torch.cat([tup[i][0 * config.num_beams + idx] for idx in range(config.num_beams)],dim=0) for tup in scores),dim=0).reshape(config.num_beams * config.norms_subset_size, tokenizer.vocab_size) for i in range(config.max_new_tokens)),
            "portability_one_hop": tuple(torch.cat(tuple(torch.cat([tup[i][0 * config.num_beams + idx] for idx in range(config.num_beams)],dim=0) for tup in scores),dim=0).reshape(config.num_beams * config.norms_subset_size, tokenizer.vocab_size) for i in range(config.max_new_tokens)),
            "portability_two_hop": tuple(torch.cat(tuple(torch.cat([tup[i][0 * config.num_beams + idx] for idx in range(config.num_beams)],dim=0) for tup in scores),dim=0).reshape(config.num_beams * config.norms_subset_size, tokenizer.vocab_size) for i in range(config.max_new_tokens)),
            "locality_neighborhood": tuple(torch.cat(tuple(torch.cat([tup[i][0 * config.num_beams + idx] for idx in range(config.num_beams)],dim=0) for tup in scores),dim=0).reshape(config.num_beams * config.norms_subset_size, tokenizer.vocab_size) for i in range(config.max_new_tokens)),
            "locality_distracting": tuple(torch.cat(tuple(torch.cat([tup[i][0 * config.num_beams + idx] for idx in range(config.num_beams)],dim=0) for tup in scores),dim=0).reshape(config.num_beams * config.norms_subset_size, tokenizer.vocab_size) for i in range(config.max_new_tokens))
        }
    
    
    return return_dict, logits_dict, scores_dict
   
   
   










# A function that calculates the labels of the sentiment analysis model on the pre_edit/post_edit model's responses
def calculate_sentiment_analysis_labels(edit_args, pre_edit, output_dict, new_ike_edit_args):
           
    negative_label = "LABEL_0"  # -1
    neutral_label =  "LABEL_1"  #  0
    positive_label = "LABEL_2"  #  1

    

    # Return {-1, 0, 1}
    # def labels_to_score(labels):
    #     if isinstance(labels, list):
    #         score = -1 * labels[0]["score"] + 0 * labels[0]["score"] + -1 * labels[0]["score"]
    
    
    
    
    def extract_highest_label(labels):
        highest = max(labels, key=lambda x: x['score'])
        return highest['label']
    
    

    # Return {-1, 0, 1}
    def label_to_int(label):
        if isinstance(label, str):
            if label == neutral_label:
                return 0
            elif label == positive_label:
                return 1
            elif label == negative_label:
                return -1
            else:
                return "Error: Invalid label"
            
        elif isinstance(label, (tuple, list)):
            return [label_to_int(l) for l in label]
    
 
    def int_to_label(value):
        if value < 0:
            return negative_label
        elif value == 0:
            return neutral_label
        else:
            return positive_label
    


    def invert_label(label):
        if label == positive_label:
            return negative_label
        elif label == negative_label:
            return positive_label
        else:
            return neutral_label
        
        
        
    # [{'label': 'LABEL_0', 'score': 0.21452203392982483}, {'label': 'LABEL_1', 'score': 0.5410013794898987}, {'label': 'LABEL_2', 'score': 0.24447660148143768}]

    def calculate_score(labels):
        # Extract scores for label_0 (negative) and label_2 (positive)
        label_0 = next(item['score'] for item in labels if item['label'] == negative_label)
        label_2 = next(item['score'] for item in labels if item['label'] == positive_label)
        
        # Calculate score: -1 * label_0 + 1 * label_2
        score = (-1 * label_0) + (1 * label_2)
        return score



    
        


    # "siebert/sentiment-roberta-large-english"
    # "distilbert/distilbert-base-uncased-finetuned-sst-2-english"

    model_name = "cardiffnlp/twitter-roberta-base-sentiment"
    sentiment_analysis = pipeline("sentiment-analysis", model=model_name, device=0)
    
    sentiment_labels_array = []
    sentiment_scores_array = []
    
    # If IKE and post_edit then change the prompts
    if config.editing_method == "IKE" and not pre_edit:
        edit_args = new_ike_edit_args
    
    
    
    for edit_index in range(config.norms_subset_size):
        

        # To work all answers in parallel
        sentiment_input = [
            edit_args["ground_truth"][edit_index],
            edit_args["target_new"][edit_index],
            *output_dict["prompt"][edit_index],
            *output_dict["light_rephrase_1"][edit_index],
            *output_dict["light_rephrase_2"][edit_index],
            *output_dict["light_rephrase_3"][edit_index],
            *output_dict["strong_rephrase"][edit_index],
            *output_dict["portability_synonym"][edit_index],
            *output_dict["portability_one_hop"][edit_index],
            *output_dict["portability_two_hop"][edit_index],
            *output_dict["locality_neighborhood"][edit_index],
            *output_dict["locality_distracting"][edit_index]
        ]
        
        # [{'label': 'LABEL_0', 'score': 0.21452203392982483}, {'label': 'LABEL_1', 'score': 0.5410013794898987}, {'label': 'LABEL_2', 'score': 0.24447660148143768}]
        # Generate predictions
        
        sentiment_output = sentiment_analysis(sentiment_input, batch_size=len(sentiment_input), return_all_scores=True)
        # sentiment_output = sentiment_analysis(sentiment_input, batch_size=len(sentiment_input))
        
        dataset_target_new_label = int_to_label(int(edit_args["action_moral_judgment"][edit_index]))
        dataset_ground_truth_label = invert_label(dataset_target_new_label)

        generated_ground_truth_label = extract_highest_label(sentiment_output[0])
        generated_target_new_label = extract_highest_label(sentiment_output[1])
        
        
        # For all return sequences
        
        prompts_labels = [extract_highest_label(sentiment_output[2 + 0 * config.num_return_sequences + idx]) for idx in range(config.num_return_sequences)]
        light_generalities_1_labels = [extract_highest_label(sentiment_output[2 + 1 * config.num_return_sequences + idx]) for idx in range(config.num_return_sequences)]
        light_generalities_2_labels = [extract_highest_label(sentiment_output[2 + 2 * config.num_return_sequences + idx]) for idx in range(config.num_return_sequences)]
        light_generalities_3_labels = [extract_highest_label(sentiment_output[2 + 3 * config.num_return_sequences + idx]) for idx in range(config.num_return_sequences)]
        
        strong_generalities_labels = [extract_highest_label(sentiment_output[2 + 4 * config.num_return_sequences + idx]) for idx in range(config.num_return_sequences)]

        portability_synonyms_labels = [extract_highest_label(sentiment_output[2 + 5 * config.num_return_sequences + idx]) for idx in range(config.num_return_sequences)]
        portability_one_hops_labels = [extract_highest_label(sentiment_output[2 + 6 * config.num_return_sequences + idx]) for idx in range(config.num_return_sequences)]
        portability_two_hops_labels = [extract_highest_label(sentiment_output[2 + 7 * config.num_return_sequences + idx]) for idx in range(config.num_return_sequences)]
                
        locality_neighborhoods_labels = [extract_highest_label(sentiment_output[2 + 8 * config.num_return_sequences + idx]) for idx in range(config.num_return_sequences)]
        locality_distractings_labels = [extract_highest_label(sentiment_output[2 + 9 * config.num_return_sequences + idx]) for idx in range(config.num_return_sequences)]
        
        
        prompts_scores = [calculate_score(sentiment_output[2 + 0 * config.num_return_sequences + idx]) for idx in range(config.num_return_sequences)]
        light_generalities_1_scores = [calculate_score(sentiment_output[2 + 1 * config.num_return_sequences + idx]) for idx in range(config.num_return_sequences)]
        light_generalities_2_scores = [calculate_score(sentiment_output[2 + 2 * config.num_return_sequences + idx]) for idx in range(config.num_return_sequences)]
        light_generalities_3_scores = [calculate_score(sentiment_output[2 + 3 * config.num_return_sequences + idx]) for idx in range(config.num_return_sequences)]
        
        strong_generalities_scores = [calculate_score(sentiment_output[2 + 4 * config.num_return_sequences + idx]) for idx in range(config.num_return_sequences)]

        portability_synonyms_scores = [calculate_score(sentiment_output[2 + 5 * config.num_return_sequences + idx]) for idx in range(config.num_return_sequences)]
        portability_one_hops_scores = [calculate_score(sentiment_output[2 + 6 * config.num_return_sequences + idx]) for idx in range(config.num_return_sequences)]
        portability_two_hops_scores = [calculate_score(sentiment_output[2 + 7 * config.num_return_sequences + idx]) for idx in range(config.num_return_sequences)]
                
        locality_neighborhoods_scores = [calculate_score(sentiment_output[2 + 8 * config.num_return_sequences + idx]) for idx in range(config.num_return_sequences)]
        locality_distractings_scores = [calculate_score(sentiment_output[2 + 9 * config.num_return_sequences + idx]) for idx in range(config.num_return_sequences)]
        
        
        
        
        sentiment_labels = {
            "dataset_ground_truth_label":label_to_int(dataset_ground_truth_label),
            "dataset_target_new_label":label_to_int(dataset_target_new_label),
            "generated_ground_truth_label":label_to_int(generated_ground_truth_label),
            "generated_target_new_label":label_to_int(generated_target_new_label),
            "prompt":label_to_int(prompts_labels),
            "light_generality_1":label_to_int(light_generalities_1_labels),
            "light_generality_2":label_to_int(light_generalities_2_labels),
            "light_generality_3":label_to_int(light_generalities_3_labels),
            "strong_generality":label_to_int(strong_generalities_labels),
            "portability_synonym":label_to_int(portability_synonyms_labels),
            "portability_one_hop":label_to_int(portability_one_hops_labels),
            "portability_two_hop":label_to_int(portability_two_hops_labels),
            "locality_neighborhood":label_to_int(locality_neighborhoods_labels),
            "locality_distracting":label_to_int(locality_distractings_labels)
        }
        
        
        sentiment_scores = {
            "dataset_ground_truth_label":label_to_int(dataset_ground_truth_label),
            "dataset_target_new_label":label_to_int(dataset_target_new_label),
            "prompt":prompts_scores,
            "light_generality_1":light_generalities_1_scores,
            "light_generality_2":light_generalities_2_scores,
            "light_generality_3":light_generalities_3_scores,
            "strong_generality":strong_generalities_scores,
            "portability_synonym":portability_synonyms_scores,
            "portability_one_hop":portability_one_hops_scores,
            "portability_two_hop":portability_two_hops_scores,
            "locality_neighborhood":locality_neighborhoods_scores,
            "locality_distracting":locality_distractings_scores
        }
    
        sentiment_labels_array.append(sentiment_labels)
        sentiment_scores_array.append(sentiment_scores)
    
    return sentiment_labels_array, sentiment_scores_array






def measure_sentiment_edit_success(pre_edit_label, post_edit_label, target_new_label) -> float:
    
    """
    This is a function that calculates the edit success based on the pre_edit, post_edit and target_new labels.
    
    This makes sure that we take into account the initial knowledge of the model and only the ground_truth in the dataset,
    which could be different from the pre_edit_model's knowledge.
    
    We have 3 labels pos, neg and neut as -1, 0 and 1 respectively
    
    We are not interested in the ground_truth of the dataset but in the ground_truth of the model itself
    This is the pre_edit_model response itself
    
    So the variables are pre_edit_label, post_edit_label and target_new, which is the expected post_edit_label
    
    | pre_edit_label |   target_new_label   | post_edit_label   | result
    |      pos       |        pos           |      pos          |  100%
    |      pos       |        pos           |      neg          |  0%
    |      pos       |        pos           |      neut         |  0%
    
    |      pos       |        neg           |      pos          |  0%
    |      pos       |        neg           |      neg          |  100%
    |      pos       |        neg           |      neut         |  50%     # Removed after careful thoughts
                   
    |      neg       |        pos           |      pos          |  100%
    |      neg       |        pos           |      neg          |  0%
    |      neg       |        pos           |      neut         |  50%     # Removed after careful thoughts
                   
    |      neg       |        neg           |      pos          |  0%
    |      neg       |        neg           |      neg          |  100%
    |      neg       |        neg           |      neut         |  0%
                   
    |      neut      |        pos           |      pos          |  100%
    |      neut      |        pos           |      neg          |  0%
    |      neut      |        pos           |      neut         |  0%
                   
    |      neut      |        neg           |      pos          |  0%
    |      neut      |        neg           |      neg          |  100%
    |      neut      |        neg           |      neut         |  0%
    
    The result will be based on this table
    
    Edit success is a ↑ metric
    
    """
          
    # Return {-1, 0, 1}
    def normalize_int_label(int_label):
        if int_label > 0:
            return 1
        elif int_label < 0:
            return -1
        else:
            return 0
            
            
    if isinstance(pre_edit_label, int):
        
        # Normalize labels to -1, 0, 1 format for comparison and calculation of success rate/change rate
        pre_edit_label = normalize_int_label(pre_edit_label)
        target_new_label = normalize_int_label(target_new_label)
        post_edit_label = normalize_int_label(post_edit_label)
        
        # 100% cases
        if target_new_label == post_edit_label:
            return 1
        
        # # 50% cases
        # elif post_edit_label == 0 and pre_edit_label != 0 and target_new_label != 0 and pre_edit_label != target_new_label:
        #     return 0.5
        
        # 0% cases
        else:
            return 0
    
    elif isinstance(pre_edit_label, (list, tuple)):
        return [measure_sentiment_edit_success(e, o, target_new_label) for e, o in zip(pre_edit_label, post_edit_label)]
    
    
    
    
    
    
    
    
    
def measure_sentiment_locality(pre_edit_label, post_edit_label, target_new_label=None) -> float:
    
    """
    This is a function that calculates the changes within the respones of the 
    pre_edit and post_edit models for the locality metric.
    
    We have 3 labels pos, neg and neut as -1, 0 and 1 respectively
    
    We are not interested in the ground_truth and target_new of the dataset
    
    So the variables are pre_edit_label, post_edit_label
    
    | pre_edit_label |    post_edit_label   | change
    |      pos       |         pos          |  0%
    |      pos       |         neg          |  100%
    |      pos       |         neut         |  50%     # Removed after careful thoughts
    |      neg       |         pos          |  100%
    |      neg       |         neg          |  0%
    |      neg       |         neut         |  50%     # Removed after careful thoughts         
    |      neut      |         pos          |  50%     # Removed after careful thoughts
    |      neut      |         neg          |  50%     # Removed after careful thoughts
    |      neut      |         neut         |  0%
    
    The result will be based on this table
    
    This locality metric is a ↓ metric
    
    """
    
    # Return {0, 0.5, 1} to get change as percentage
    def normalize_int_label(int_label):
        if int_label > 0:
            return 1
        elif int_label < 0:
            return 0
        else:
            return 0.5
        
    if isinstance(pre_edit_label, int):
    
        # Normalize labels to 0, 0.5, 1 format for comparison and calculation of success rate/change rate
        pre_edit_label = normalize_int_label(pre_edit_label)
        post_edit_label = normalize_int_label(post_edit_label)
        
        return int(pre_edit_label != post_edit_label)
        
        
        # return abs(pre_edit_label - post_edit_label)
    
    elif isinstance(pre_edit_label, (list, tuple)):
        return [measure_sentiment_locality(e, o) for e, o in zip(pre_edit_label, post_edit_label)]
    
    
    
    
    
def measure_score_difference(pre, post, target_new_label, locality):
    if isinstance(pre,(int, float)):
        if locality:
            return abs(post - pre)
        else:
            if target_new_label == 1:
                return post - pre
            else:
                return pre - post
    elif isinstance(pre,(list, tuple)):
        return [measure_score_difference(e, o, target_new_label, locality) for e, o in zip(pre, post)]

    
    
    


def evaluate_sentiment_metric(pre_edit_sentiment_labels, pre_edit_sentiment_scores, post_edit_sentiment_labels, post_edit_sentiment_scores):
    

    def format_output_labels(pre_edit_item, post_edit_item, key, label_to_use, result):
        return f"pre: {pre_edit_item[key]} --> post: {post_edit_item[key]} == should be: {label_to_use} => result: {result}"

    
    def format_output_scores(pre_edit_item, post_edit_item, key, result):
        return f"pre: {pre_edit_item[key]} --> post: {post_edit_item[key]} => result: {result}"

    # Labels
    sentiment_labels_changes_metric = []
    
    for pre_edit_item, post_edit_item in zip(pre_edit_sentiment_labels, post_edit_sentiment_labels):
        
        item = {}
        eval_func = measure_sentiment_edit_success
        
        dataset_target_new_label = pre_edit_item["dataset_target_new_label"]
        dataset_ground_truth_label = pre_edit_item["dataset_ground_truth_label"]
        label_to_use = dataset_target_new_label
        
        for key in pre_edit_item:
            
            if key == "portability_two_hop":
                label_to_use = dataset_ground_truth_label
            else:
                label_to_use = dataset_target_new_label
            
            if key in ["dataset_ground_truth_label", "dataset_target_new_label", "generated_ground_truth_label", "generated_target_new_label"]:
                continue
            
            elif key in ["sentiment_analysis_model_reliability", "locality_neighborhood", "locality_distracting"]:
                eval_func = measure_sentiment_locality
                
            else:
                eval_func = measure_sentiment_edit_success
            
            result = eval_func(pre_edit_item[key], post_edit_item[key], label_to_use)
            
            item.update({key : format_output_labels(pre_edit_item, post_edit_item, key, label_to_use, result)})

        sentiment_labels_changes_metric.append(item)
        
        
        
        
    # scores   
    sentiment_scores_changes_metric = []
    
    for pre_edit_item, post_edit_item in zip(pre_edit_sentiment_scores, post_edit_sentiment_scores):
        
        item = {}
        
        for key in pre_edit_item:
            
            dataset_target_new_label = pre_edit_item["dataset_target_new_label"]
            dataset_ground_truth_label = pre_edit_item["dataset_ground_truth_label"]
            label_to_use = dataset_target_new_label
            
            locality = False
            
            if key == "portability_two_hop":
                label_to_use = dataset_ground_truth_label
            
            if key in ["dataset_ground_truth_label", "dataset_target_new_label", "generated_ground_truth_label", "generated_target_new_label"]:
                continue
            
            if key in ["locality_neighborhood", "locality_distracting"]:
                locality = True
                
            result = measure_score_difference(pre_edit_item[key], post_edit_item[key], label_to_use, locality) 
            item.update({key : format_output_scores(pre_edit_item, post_edit_item, key, result)})

        sentiment_scores_changes_metric.append(item)
        
        
    
    return sentiment_labels_changes_metric, sentiment_scores_changes_metric








def find_first_differing_token(tokenizer, pre_edit_output_dict_item, post_edit_output_dict_item, locality_prompt, ike_locality_prompt = None):
    """
    Finds the first token position where the predicted tokens start to differ 
    between two pre/post edit sequences.

    Returns:
        List of differing positions for each element. If no difference, returns -1.
    """
    differing_positions = [[-1]*config.num_return_sequences] * config.norms_subset_size  # Default to -1 if no difference found
    
    # Iterate over the token logits
    for edit_index in range(config.norms_subset_size):  
        for sequence_index in range(config.num_return_sequences):
            
            # Find the identical parts of pre/post edit sequences
            index , common_sentence = common_prefix(pre_edit_output_dict_item[edit_index][sequence_index][len(locality_prompt[edit_index]):], post_edit_output_dict_item[edit_index][sequence_index][len(locality_prompt[edit_index]):])

            # Cut the length of the IKE template
            if config.editing_method == "IKE":
                index , common_sentence = common_prefix(pre_edit_output_dict_item[edit_index][sequence_index][len(locality_prompt[edit_index]):], post_edit_output_dict_item[edit_index][sequence_index][len(ike_locality_prompt[edit_index]):])
            
            # Convert strings into tokens and count their number
            number_of_common_tokens = count_tokens(tokenizer, common_sentence)
            differing_positions[edit_index][sequence_index] = number_of_common_tokens - 1
            
            if index == -1:
                differing_positions[edit_index][sequence_index] = -1
            
    return differing_positions  # List of first differing token positions for each batch








def evaluate_kl_div_metric(tokenizer, pre_edit_logits_dict, post_edit_logits_dict, pre_edit_output_dict, post_edit_output_dict, norms_dict, new_edit_args = None):
    """
    Finds the first token, at which the pre_edit and post_edit responses begin to differ
    and calculate the kl divergence at this point exactly.
    
    Get every element of the batch and do the process seperately, then average the result.
    
    """


    def format_output(item):
        return item
    
    
    kl_div_dict = {}

    
    # iterate only over locality keys
    for key in ["locality_neighborhood", "locality_distracting"]:
        
        differing_token_indices = 0
        
        if config.editing_method == "IKE":
            differing_token_indices = find_first_differing_token(tokenizer, pre_edit_output_dict[f"unformatted_{key}"], post_edit_output_dict[f"unformatted_{key}"], norms_dict["locality_inputs"][key.split("_")[1]]["prompt"], new_edit_args["locality_inputs"][key.split("_")[1]]["prompt"])
        else:
            differing_token_indices = find_first_differing_token(tokenizer, pre_edit_output_dict[f"unformatted_{key}"], post_edit_output_dict[f"unformatted_{key}"], norms_dict["locality_inputs"][key.split("_")[1]]["prompt"], None)


        result_per_key = []
        
        # iterate over edits and sequences (batch/number_of_norms * num_beams)
        for edit_index in range(config.norms_subset_size):
            result_per_edit = []
            
            for sequence_index in range(config.num_return_sequences):
                
                current_index = sequence_index + config.num_return_sequences * edit_index
                differing_token_index = differing_token_indices[edit_index][sequence_index]
                differing_token_index_temp = differing_token_index
                
                # If no difference found, calculate the kl div at the first token
                if differing_token_index == -1:
                    differing_token_index = 0
            
                
                kl_div_first_token = calculate_kl_divergence_for_token(pre_edit_logits_dict[key], post_edit_logits_dict[key], current_index, 0).item()
                kl_div_differing_token = calculate_kl_divergence_for_token(pre_edit_logits_dict[key], post_edit_logits_dict[key], current_index, differing_token_index).item()
            
                
                item_dict = {
                    "kl_div_first_token" : kl_div_first_token,
                    "kl_div_differing_token" : kl_div_differing_token,
                    "kl_div_differing_token_index" : differing_token_index_temp,
                }
                
                result_per_edit.append(item_dict)
            
            result_per_key.append(result_per_edit)
            
        kl_div_dict.update({f"kl_div_{key}":format_output(result_per_key)})
    
    
    return kl_div_dict







def calculate_perplexity(tokenizer, model, input_text):
    
    # Tokenize input
    inputs = tokenizer(input_text, return_tensors="pt", truncation=True, max_length=config.max_length).to(model.device)
    input_ids = inputs["input_ids"]
    attention_mask = inputs["attention_mask"]

    # Compute loss without training
    with torch.no_grad():
        outputs = model(input_ids=input_ids, attention_mask=attention_mask, labels=input_ids)
        loss = outputs.loss

    # Compute perplexity
    perplexity = torch.exp(loss)
    
    return perplexity.item()








def calculate_perplexity_for_locality(tokenizer, model, output_dict, norms_dict =  None, new_ike_edit_args = None):
    
    # One item for each edit
    edits_effect_list = []
    
    # Iterate over edits
    for i in range(config.norms_subset_size):
        
        edit_effect_neighborhood_items = []
        edit_effect_distracting_items = []
        
        for j in range(config.num_return_sequences):
            
            neighborhood_sequence = output_dict["unformatted_locality_neighborhood"][i][j]
            distracting_sequence =  output_dict["unformatted_locality_distracting"][i][j]
            
            # If IKE and post edit, calculate perpl for the pre edit answer but with the prompt with the IKE template 
            if config.editing_method == "IKE" and norms_dict and new_ike_edit_args:
                                
                loc_neighborhood_prompt_length = len(norms_dict["locality_inputs"]["neighborhood"]["prompt"][i])
                loc_distracting_prompt_length = len(norms_dict["locality_inputs"]["neighborhood"]["prompt"][i])
                
                neighborhood_sequence = new_ike_edit_args["locality_inputs"]["neighborhood"]["prompt"][i] + output_dict["unformatted_locality_neighborhood"][i][j][loc_neighborhood_prompt_length:]
                distracting_sequence = new_ike_edit_args["locality_inputs"]["distracting"]["prompt"][i] + output_dict["unformatted_locality_distracting"][i][j][loc_distracting_prompt_length:]
                

            perplexity_neighborhood = calculate_perplexity(tokenizer, model, neighborhood_sequence)
            perplexity_distracting = calculate_perplexity(tokenizer, model, distracting_sequence)

            edit_effect_neighborhood_items.append(perplexity_neighborhood)
            edit_effect_distracting_items.append(perplexity_distracting)

        edit_effects_item = {
            "locality_neighborhood_perplexity": edit_effect_neighborhood_items,
            "locality_distracting_perplexity": edit_effect_distracting_items,
        }
        
        edits_effect_list.append(edit_effects_item)

    return edits_effect_list








def evaluate_perplexity_metric(pre_edit_perplexity_metric, post_edit_perplexity_metric):
    
    def format_output(pre_edit_item, post_edit_item, key, results):
        return f"pre: {pre_edit_item[key]} --> post: {post_edit_item[key]} --> {results}"


    def absolute_eval_func(pre_edit_item, post_edit_item):
        if isinstance(pre_edit_item, float):
            return post_edit_item - pre_edit_item
        elif isinstance(pre_edit_item,list):
            return [absolute_eval_func(pr, po) for pr, po in zip(pre_edit_item, post_edit_item)]
        
        
    def relative_eval_func(pre_edit_item, post_edit_item):
        if isinstance(pre_edit_item, float):
            return post_edit_item / pre_edit_item
        elif isinstance(pre_edit_item,list):
            return [relative_eval_func(pr, po) for pr, po in zip(pre_edit_item, post_edit_item)]
    
    
    edit_effect_perplexity_metric = []
    
    
    # Iterate over edits
    for pre_edit_item, post_edit_item in zip(pre_edit_perplexity_metric, post_edit_perplexity_metric):
        
        item = {}
    
        for key in pre_edit_item:
            
            absoulte_results = absolute_eval_func(pre_edit_item[key], post_edit_item[key])
            relative_results = relative_eval_func(pre_edit_item[key], post_edit_item[key])
            
            item.update({f"absolute_{key}" : format_output(pre_edit_item, post_edit_item, key, absoulte_results)})
            item.update({f"relative_{key}" : format_output(pre_edit_item, post_edit_item, key, relative_results)})

        edit_effect_perplexity_metric.append(item)
    
    return edit_effect_perplexity_metric













def measure_quality_chatgpt_api(edit_args, decoded_post_edit_response):
    template = f"{decoded_post_edit_response}"
    response = send_request(template)









# ---------------------------------------------------------------- #
# ---------------------------------------------------------------- #
# -----------------Utils for debugging purposes------------------- #
# ---------------------------------------------------------------- #
# ---------------------------------------------------------------- #




def analyse_reliability_of_edit(decoded_post_edit_response,target_new) -> str:

    output = ""
    edit_successfull =  target_new.lower() in decoded_post_edit_response.lower()
    check1 = f"Does the post_edit_answer contain the target answer? {edit_successfull}"
    log(check1,True,True,True)
    output += check1 + "\n"

    return output




def check_model_weights_changed(pre_edit_model, post_edit_model):
    if pre_edit_model and post_edit_model:
        output = "The models are the same."
        for parameter_name, parameter_value in pre_edit_model.state_dict().items():
            if not torch.equal(parameter_value, post_edit_model.state_dict()[parameter_name]):
                output = "The models are different."
                
        log(output,True,True,True)
        return output
    
    
    
    
    
    
def output_debugging_info(tokenizer, pre_edit_model, post_edit_model, edit_args, pre_edit_output_dict, post_edit_output_dict, pre_edit_logits_dict, post_edit_logits_dict, pre_edit_scores_dict, post_edit_scores_dict):
    
    # Add log info
    log_info, pre_edit_scores_string, post_edit_scores_string, models_check_string = [] , "", "", ""
    
    # Some debugging information
    if config.enable_analytics:
        # for i in range(len(decoded_post_edit_response)):
        #     log_info.append(analyse_reliability_of_edit(decoded_post_edit_response=decoded_post_edit_response[i], target_new=edit_args["target_new"][i]))

        log_info.append(analyse_kl_divergence(pre_edit_logits_dict['prompt'], post_edit_logits=post_edit_logits_dict['prompt']))
        
    # Scores of the post_edit_logits
    if config.enable_output_scores:
        pre_edit_scores_string = output_token_scores(tokenizer, pre_edit_scores_dict["prompt"], 0)
        post_edit_scores_string = output_token_scores(tokenizer, post_edit_scores_dict["prompt"], 0)
        
    # Useful for debugging
    if config.enable_models_check and pre_edit_model and post_edit_model:
        models_check_string = check_model_weights_changed(pre_edit_model,post_edit_model)
    
    
    write_output_to_file("additional_information",True,*log_info, pre_edit_scores_string, post_edit_scores_string, models_check_string)
    
    
    
    
    
    
    
    
    
    
    

def load_facts():
    
    ds = load_dataset("json", data_files="datasets/facts/facts_edit_propmts_dataset.json",split='train')
    prompts = ds['prompt']
    ground_truth = ds['ground_truth']
    target_new = ds['target_new']
    subject = ds['subject']
    rephrase_prompts = ds['rephrase_prompt']
    locality_inputs = ds['locality_inputs']
    portability_inputs = ds['portability_inputs']

    locality_inputs_neighborhood_prompt_unpacked = []
    locality_inputs_neighborhood_ground_truth_unpacked = []
    locality_inputs_distracting_prompt_unpacked = []
    locality_inputs_distracting_ground_truth_unpacked = []
    
    portability_inputs_synonym_prompt_unpacked = []
    portability_inputs_synonym_ground_truth_unpacked = []
    portability_inputs_one_hop_prompt_unpacked = []
    portability_inputs_one_hop_ground_truth_unpacked = []
    
    
    # Check whether locality and portability are empty
    
    for l1 in locality_inputs:
        if len(l1['neighborhood']['prompt']) > 0:
            locality_inputs_neighborhood_prompt_unpacked.append(l1['neighborhood']['prompt'])
    for l2 in locality_inputs:
        if len(l2['neighborhood']['ground_truth']) > 0:
            locality_inputs_neighborhood_ground_truth_unpacked.append(l2['neighborhood']['ground_truth'])
    for l3 in locality_inputs:
        if len(l3['distracting']['prompt']) > 0:
            locality_inputs_distracting_prompt_unpacked.append(l3['distracting']['prompt'])
    for l4 in locality_inputs:
        if len(l4['distracting']['ground_truth']) > 0:
            locality_inputs_distracting_ground_truth_unpacked.append(l4['distracting']['ground_truth'])
        
    for p1 in portability_inputs:
        if len(p1['synonym']['prompt']) > 0:
            portability_inputs_synonym_prompt_unpacked.append(p1['synonym']['prompt'])
    for p2 in portability_inputs:
        if len(p2['synonym']['ground_truth']) > 0:
            portability_inputs_synonym_ground_truth_unpacked.append(p2['synonym']['ground_truth'])
    for p3 in portability_inputs:
        if len(p3['one_hop']['prompt']) > 0:
            portability_inputs_one_hop_prompt_unpacked.append(p3['one_hop']['prompt'])
    for p4 in portability_inputs:
        if len(p4['one_hop']['ground_truth']) > 0:
            portability_inputs_one_hop_ground_truth_unpacked.append(p4['one_hop']['ground_truth'])
    
    locality_inputs = {}
    portability_inputs = {}
    
    if len(locality_inputs_neighborhood_prompt_unpacked) > 0 and len(locality_inputs_distracting_prompt_unpacked) > 0:
        locality_inputs = {
            "neighborhood":{
                "prompt": locality_inputs_neighborhood_prompt_unpacked,
                "ground_truth": locality_inputs_neighborhood_ground_truth_unpacked
            },
            "distracting":{
                "prompt": locality_inputs_distracting_prompt_unpacked,
                "ground_truth": locality_inputs_distracting_ground_truth_unpacked
            }
	    }         
    elif len(locality_inputs_neighborhood_prompt_unpacked) > 0:
        locality_inputs = {
            "neighborhood":{
                "prompt": locality_inputs_neighborhood_prompt_unpacked,
                "ground_truth": locality_inputs_neighborhood_ground_truth_unpacked
            },
	    }
    elif len(locality_inputs_distracting_prompt_unpacked) > 0:
        locality_inputs = {
            "distracting":{
                "prompt": locality_inputs_distracting_prompt_unpacked,
                "ground_truth": locality_inputs_distracting_ground_truth_unpacked
            }
	    }
        
        
        
    if len(portability_inputs_synonym_prompt_unpacked) > 0 and len(portability_inputs_one_hop_prompt_unpacked) > 0:
        portability_inputs = {
            "synonym":{
                "prompt": portability_inputs_synonym_prompt_unpacked,
                "ground_truth":portability_inputs_synonym_ground_truth_unpacked
            },
            "one_hop":{
                "prompt": portability_inputs_one_hop_prompt_unpacked,
                "ground_truth": portability_inputs_one_hop_ground_truth_unpacked
            }
        }         
    elif len(portability_inputs_synonym_prompt_unpacked) > 0:
        portability_inputs = {
            "synonym":{
                "prompt": portability_inputs_synonym_prompt_unpacked,
                "ground_truth": portability_inputs_synonym_ground_truth_unpacked
            },
        }
    elif len(portability_inputs_one_hop_prompt_unpacked) > 0:
        portability_inputs = {
            "one_hop":{
                "prompt": portability_inputs_one_hop_prompt_unpacked,
                "ground_truth": portability_inputs_one_hop_ground_truth_unpacked
            }
        }
        
    
    log("Facts dataset loaded",False,False,True)

    return prompts, ground_truth, target_new, subject, rephrase_prompts, locality_inputs, portability_inputs












def calculate_kl_divergence_amongst_all_tokens(pre_edit_logits, post_edit_logits, element_index):
    result = 0
    biggest_kl_divergence = 0
    biggest_kl_divergence_index = 0
    
    for i in range(len(pre_edit_logits)):
        current_kl_divergence = calculate_kl_divergence_for_token(pre_edit_logits,post_edit_logits, element_index, i).item()
        result += current_kl_divergence

        if current_kl_divergence > biggest_kl_divergence:
            biggest_kl_divergence = current_kl_divergence
            biggest_kl_divergence_index = i
        
    return biggest_kl_divergence, biggest_kl_divergence_index, result







def analyse_kl_divergence(pre_edit_logits,post_edit_logits) -> str:
    output = ""
    if pre_edit_logits and post_edit_logits and config.editing_method != "IKE":
        kl_div_first_token = calculate_kl_divergence_for_token(pre_edit_logits,post_edit_logits, 2)
        biggest_div, biggest_div_index, kl_div_all_tokens = calculate_kl_divergence_amongst_all_tokens(pre_edit_logits,post_edit_logits, 0)
        check2 = f"KL divergence for first token: {kl_div_first_token}"
        check3 = f"KL divergence amongst all tokens: {kl_div_all_tokens}"
        check4 = f"Biggest KL divergence is on token {biggest_div_index} with the value of {biggest_div}"
        log(check2,True,True,True)
        log(check3,True,True,True)
        log(check4,True,True,True)
        output += check2 + "\n" + check3 + "\n" + check4 + "\n"

    return output




# def test_generation_quality(
#     model,
#     tok,
#     prefixes: typing.List[str],
#     max_out_len: int,
#     vanilla_generation: bool = False,
# ):
#     gen_texts = generate_fast(
#         model,
#         tok,
#         prefixes,
#         n_gen_per_prompt=1,
#         max_out_len=max_out_len,
#         vanilla_generation=vanilla_generation,
#     )

#     ngram_entropy = n_gram_entropy(gen_texts)
#     ret = {
#         "ngram_entropy": ngram_entropy,
#     }
#     return ret

# def n_gram_entropy(gen_texts, agg="arith"):
#     assert agg in ["arith", "geom"]

#     return (scipy.stats.mstats.gmean if agg == "geom" else np.mean)(
#         [compute_n_gram_entropy(txt) for txt in gen_texts]
#     ).item()

# def compute_n_gram_entropy(sentence, ns=None, weights=None, agg="arith"):
#     if ns is None:
#         ns = [2, 3]
#     if weights is None:
#         weights = [2 / 3, 4 / 3]
#     assert agg in ["arith", "geom"]

#     entropy_list = []
#     for n in ns:
#         fdist = compute_freq(sentence, n)
#         freqs = np.array([freq for _, freq in fdist.items()])
#         freqs = freqs / freqs.sum()

#         entropy_list.append(np.sum(-freqs * np.log(freqs) / np.log(2)))

#     entropy_list = np.array(entropy_list) * np.array(weights)

#     return (scipy.stats.mstats.gmean if agg == "geom" else np.mean)(entropy_list)