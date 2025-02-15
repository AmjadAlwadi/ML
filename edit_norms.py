from transformers import AutoTokenizer, AutoModelForCausalLM
from huggingface_hub import login
from transformers import set_seed
import torch
import time
import argparse
import warnings 
import os
from colorama import Fore, Back, Style, init

import config
from utils import *
from evaluation import *
from edit import edit


# TODO:


# Final touches in cutsom metric
# Calculate KL div for locality


# Try backtranslation technique using vllm   Done
# Try causal tracing and argument that it is not useful since every we only have a rot which is every time of different structure Done
# We have no subjects  Done

# Fix IKE for norms  
# Add situation to prompt in the edit norms dataset  Done
# Add locality prompts as an original norm   Done

# Fix the edit norms dataset   Done
## Change the structure       Done


# Generate rephrases using o3 api or using tubs   #DONE
# Find out what to do with subject for ROME  --> Pick for example the action always???    Done


# Find out the difference between locality neighborhood and locality distracting     #DONE
## locality neighborhood are prompts with the same relation and object as the edit but different subjects 

# These neighborhood
# prompts can be used to inspect whether the model   
# edit has undesired side effects on closely related
# factual associations

## locality distrcting neighborhood is similar with a distracting statement at the beginning which is the edited prompt
## Relations in facts are based on the wikidata relation types and there are too many
## In our case of norms we only have one relation or one type of statements

# Add api icl chatgpt4     # Not really necessary

# Try instead of rephrasing backtranslation technique  Done

# Change loading in edit        Done
# Fix generating edit norms dataset and fix locality   Done



# MAybe fix subject difference in im/moral actions and ground_truth


# For the custom metric cut the response till the point



# Trian MEND on the norms dataset

# write an extra file for the difference of the evaluations
# To take into account the initial knowledge of the model

# Make the locality prompts those that have contrary action judgement
# not necessarily good btw
# Add KL divergence to the final locality

def main():
    
    # Some initializations
    init()
    os.makedirs('outputs/', exist_ok=True)

    # Ignore all warnings
    warnings.filterwarnings("ignore")
    
    if not torch.cuda.is_available() and config.device != torch.device('cpu'):
        print("Torch cuds is not available")
        return
    
    login(token=config.access_token,add_to_git_credential=True)
    
    if config.seed != -1:
        set_seed(config.seed)

    tokenizer = AutoTokenizer.from_pretrained(config.model_name)
    
    tokenizer.padding_side='left'
    if tokenizer.pad_token is None:
        tokenizer.pad_token_id = tokenizer.eos_token_id
        
    
    # Change into dict
    
    # Load the edit norms dataset
    norms_dict = load_norms()
    

    # Some global variables
    pre_edit_model, post_edit_model = None, None
    # post_edit_easy_edit_metrics = None
    pre_edit_custom_metric = None
    post_edit_custom_metric = None
    ike_generation_prompts = []


    # ---------------------------------------------------------------- #
    # ----------------------Editing process--------------------------- #
    # ---------------------------------------------------------------- #
    
        
    # Initialize the arguments dictionary
    edit_args = {
        "prompts": norms_dict["prompts"],
        "ground_truth": norms_dict["ground_truth"],
        "target_new": norms_dict["target_new"],
        "subject": norms_dict["subject"],
        "locality_inputs": norms_dict["locality_inputs"],
        "locality_inputs_action_moral_judgement" : norms_dict["locality_inputs_action_moral_judgement"],
        "rephrase_prompts": norms_dict["strong_rephrase_prompts"],
        "portability_inputs": norms_dict["portability_inputs"],
        "sequential_edit": True,
        "loc_prompts" : norms_dict["loc_prompts"],
        
        "moral_action": norms_dict["moral_action"],
        "immoral_action": norms_dict["immoral_action"],
        "action_moral_judgment": norms_dict["action_moral_judgment"],
        "light_rephrase_prompts": norms_dict["light_rephrase_prompts"],
        "strong_rephrase_prompts": norms_dict["strong_rephrase_prompts"]
    }
            
    
    post_edit_easy_edit_metrics, post_edit_model, editing_time = edit(edit_args, tokenizer, ike_generation_prompts)    
          
    
    if config.train:
        log(f"Training took {editing_time:.2f} seconds.",False,False,True)
        return
    else:
        log(f"Editing took {editing_time:.2f} seconds.",False,False,True)
        
         
         
    # ---------------------------------------------------------------- #
    # ----------------------Evaluation process------------------------ #
    # ---------------------------------------------------------------- #
        
     
    # Saving the post edit metrics of Easy Edit 
    save_as_json(post_edit_easy_edit_metrics,"post_edit_easy_edit_metrics")
    log("Metrics saved as json file",False,False,False)
    log("Loaded edited model",True,False,True)
    print_gpu_memory()    
          
    
    # All needed outputs for post_edit_model
    post_edit_output_dict = preprare_responses(tokenizer, None, post_edit_model, edit_args)
    
    # Write post_edit_response to a file
    post_edit_logs = edit_args | {k: v for k, v in post_edit_output_dict.items() if k != "logits"}
    save_as_json(post_edit_logs,"post_edit_logs")

    
    # FIX IKE HERE
        
    # Calculate the custom metric for post_edit_model
    if config.editing_method == "IKE":
        
        # Load the pre_edit_model    
        pre_edit_model = load_pre_edit_model()
        
        # # Modify the prompt according to template and create response
        # post_edit_response = create_response(pre_edit_model, tokenizer, ike_generation_prompts, instructinoal=False)
        
        # for sequence,prompt in zip(post_edit_response.sequences,ike_generation_prompts):
        #     decoded_post_edit_response.append(decode_output_and_log(tokenizer=tokenizer, output=sequence, question=prompt, pre_edit=False))
              
    else:   
        
        if config.calculate_custom_metric_for_post_edit_model:
            post_edit_custom_metric = measure_quality_sentiment_analysis(edit_args, False, post_edit_output_dict)
            save_as_json(post_edit_custom_metric,"post_edit_custom_metric")
            
        
        
    # Unload post_edit_model if not used later
    unload_post_edit_model(post_edit_model)
        
        
    # Custom metric calculation for pre_edit_model
    if config.calculate_custom_metric_for_pre_edit_model:
        
        # Load the pre_edit_model if needed
        if not pre_edit_model:
            pre_edit_model = load_pre_edit_model()
            
        # All needed outputs for pre_edit_model
        pre_edit_output_dict = preprare_responses(tokenizer, pre_edit_model, None, edit_args)
        
        # Write post_edit_response to a file
        pre_edit_logs = edit_args | {k: v for k, v in pre_edit_output_dict.items() if k != "logits"}
        save_as_json(pre_edit_logs,"pre_edit_logs")

        pre_edit_custom_metric = measure_quality_sentiment_analysis(edit_args, True, pre_edit_output_dict)
        save_as_json(pre_edit_custom_metric,"pre_edit_custom_metric")
        
    
    # Show the effects of the edit
    if config.calculate_custom_metric_for_pre_edit_model and config.calculate_custom_metric_for_post_edit_model:
        edit_difference_custom_metric = [{key: f"{pre_edit_item[key]:.3f} --> {post_edit_item[key]:.3f} = {(abs(pre_edit_item[key] + post_edit_item[key])%2)*100:.2f}% Changes" for key in pre_edit_item if key not in ["sentiment_analysis_model_reliability"]} for pre_edit_item, post_edit_item in zip(pre_edit_custom_metric, post_edit_custom_metric)]
        save_as_json(edit_difference_custom_metric,"edit_difference_custom_metric")
     
     
    # Unload pre_edit_model if not used later
    unload_pre_edit_model(pre_edit_model)
        
    
    # Output scores, KL divergence and other useful information
    # output_debugging_info(tokenizer, pre_edit_model, post_edit_model, edit_args, pre_edit_output_dict, post_edit_output_dict)


    # Freely chat with the post edit model
    if config.freely_chat_with_post_edit_model:
        chat_with_model(post_edit_model,tokenizer)





def parse_arguments():
    
    parser = argparse.ArgumentParser(description="Model Editing Script")
    
    
    parser.add_argument("-e","--editing_method", type=str, default="No editing", choices=list(config.available_editing_methods.values()),
                        help="Editing method to use\nIf not specified, then no editing is performed")
    parser.add_argument("--model_name", type=str, default=config.available_models[10],
                        help="Name of the model to use")
    parser.add_argument("-n","--norms_subset_size", type=int, default=1,
                        help="Number of norms to edit")
    parser.add_argument("-f","--freely_chat", action="store_true",
                        help="Whether to freely chat with the post-edit model")
    parser.add_argument("-t","--train", action="store_true",
                        help="Train the algorithm")
    parser.add_argument("--shuffle", action="store_true",
                        help="Shuffle the dataset")
    
    # Decoding strategy parameters
    parser.add_argument("--seed", type=int, default=-1,
                        help="Random seed for reproducibility")
    parser.add_argument("--max_length", type=int, default=100,
                        help="Maximum number of tokens in the prompt")
    parser.add_argument("-m", "--max_new_tokens", type=int, default=20,
                        help="Maximum number of new tokens to generate")
    parser.add_argument("--num_beams", type=int, default=1,
                        help="Maximum number of new tokens to generate")
    parser.add_argument("--do_sample", action="store_true",
                        help="Activate multinomial-sampling")
    parser.add_argument("--early_stopping", action="store_true",
                        help="Early stopping")
    parser.add_argument("--no_repeat_ngram_size", type=int, default=0,
                        help="No repeat ngram size")
    
    # Debugging stuff
    parser.add_argument("--enable_analytics", action="store_true",
                        help="Show the KL divergence and more")
    parser.add_argument("--enable_models_check", action="store_true",
                        help="Check whether the post_edit model did change")
    
    # Extra information
    parser.add_argument("--enable_output_scores", action="store_true",
                        help="Show the scores for the most probable tokens")
    parser.add_argument("--top_k", type=int, default=10,
                        help="Top k probable tokens for the output scores")
    
    parser.add_argument("-b","--calculate_custom_metric_for_post_edit_model", action="store_true",
                        help="Acitvate the custom metric calculation for edited model")
    parser.add_argument("-a","--calculate_custom_metric_for_pre_edit_model", action="store_true",
                        help="Acitvate the custom metric calculation for pre_edit_model")
    
    
    parser.add_argument("--enable_cpu_inference", action="store_true",
                        help="Whether to do the inference on the CPU")
    parser.add_argument("-w",'--weights_dtype', type=str, choices=['float32', 'float16', 'bfloat16'],
                        default='float32', help='Data type for weights: float32, 16 or bfloat16' )
    parser.add_argument("--config_file_name", type=str, default=config.available_models[10].split("/")[1],
                        help="Name of the config file")
    
    args = parser.parse_args()
    
    
    # Update global variables
    config.editing_method = args.editing_method
    config.model_name = args.model_name
    config.freely_chat_with_post_edit_model = args.freely_chat
    config.norms_subset_size = args.norms_subset_size
    
    args.config_file_name = config.model_name.split("/")[1]
    
    config.hparams_path =  os.path.join(get_ml_path(), "hparams", config.editing_method, f"{args.config_file_name}.yaml")
    config.train_hparams_path = os.path.join(get_ml_path(), "hparams", "TRAINING", config.editing_method, f"{args.config_file_name}.yaml")
    
    dtype_map = { 'float32': torch.float32, 'float16': torch.float16, 'bfloat16': torch.bfloat16 }
    config.weights_dtype = dtype_map[args.weights_dtype]
    
    config.seed = args.seed
    config.max_new_tokens = args.max_new_tokens
    config.max_length = args.max_length
    config.num_beams = args.num_beams
    config.no_repeat_ngram_size = args.no_repeat_ngram_size
    config.early_stopping = args.early_stopping
    config.do_sample = args.do_sample
    config.top_k = args.top_k
    config.apply_edit = True
    config.train = args.train
    config.enable_analytics = args.enable_analytics
    config.enable_output_scores = args.enable_output_scores
    config.enable_models_check = args.enable_models_check
    config.calculate_custom_metric_for_post_edit_model = args.calculate_custom_metric_for_post_edit_model
    config.calculate_custom_metric_for_pre_edit_model = args.calculate_custom_metric_for_pre_edit_model
        
    config.decoding_strategy = "greedy-decoding" 
    
    if config.num_beams == 1 and config.do_sample == False:
        config.decoding_strategy = "greedy-decoding"
    elif config.num_beams > 1 and config.do_sample == False:
        config.decoding_strategy = "beam-search"
    else:
        config.decoding_strategy = "multinomial-sampling"
        
    
    if not args.enable_cpu_inference:
        config.device = torch.device('cuda')
    else:
        config.device = torch.device('cpu')
    
    if config.editing_method == "No editing":
        config.apply_edit = False
        
    # We need the outputs to be able to calculate the scores
    if config.enable_output_scores:
        config.show_pre_edit_answer = True
        config.show_post_edit_answer = True
    
    config.shuffle = args.shuffle
    
    
    col_width = 27
    
    print()
    print('-'*75)
    
    print(Fore.BLUE)
    print("Edit Configuration")
    print(f"{'Model_name:':<{col_width}} {config.model_name}")
    print(f"{'Editing_method:':<{col_width}} {config.editing_method}")
    print(f"{'Decoding_strategy:':<{col_width}} {config.decoding_strategy}")
    print(f"{'Number of norms to edit:':<{col_width}} {config.norms_subset_size}")
    print(f"{'Device:':<{col_width}} {str(config.device)}")
    
    print(Fore.LIGHTYELLOW_EX)
    print("Information to Output")
    print(f"{'train:':<{col_width}} {str(config.train)}")
    print(f"{'calculate_custom_metric_for_pre_edit_model:':<{col_width}} {str(config.calculate_custom_metric_for_pre_edit_model)}")
    print(f"{'calculate_custom_metric_for_post_edit_model:':<{col_width}} {str(config.calculate_custom_metric_for_post_edit_model)}")
    
    print(Fore.CYAN)
    print("Debugging Informations")
    print(f"{'enable_output_scores:':<{col_width}} {str(config.enable_output_scores)}")
    print(f"{'enable_analytics:':<{col_width}} {str(config.enable_analytics)}")
    print(f"{'enable_models_check:':<{col_width}} {str(config.enable_models_check)}") 
    print(f"{'freely chat with model:':<{col_width}} {str(config.freely_chat_with_post_edit_model)}")
    
    print(Fore.LIGHTRED_EX)
    print("Extra Configuration")
    print(f"{'weights_dtype:':<{col_width}} {str(config.weights_dtype)}")
    print(f"{'hparams_path:':<{col_width}} {config.hparams_path}")
    print(f"{'available_gpu_memory:':<{col_width}} {str(get_available_gpu_memory())}")
    print(Style.RESET_ALL)
    print('-'*75)
    print()
    
    return args


if __name__ == '__main__':
    
    parse_arguments()
    main()