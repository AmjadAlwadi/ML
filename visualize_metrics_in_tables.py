import argparse
import json
import os
import numpy as np
import statistics
import re
from collections import defaultdict


# TODO:
# sort according to final score





kl_div_files_dict = None
sentiment_files_dict = None
perplexity_files_dict = None
headers = None

keep_editing_method=True
keep_model_name=True
keep_decoding_method = True
keep_number_of_sequential_edits = True

precision = 2


# Generate a latex table and a plot

def read_json_from_file(file):
    # Read the JSON file
    with open(file, 'r') as file:
        data = json.load(file)
        return data



def generate_latex_table(headers, rows):
    headers = [str(header) for header in headers]
    rows = [[str(value) for value in row] for row in rows]  # Fixed this

    # Start the table
    latex_table = "\\begin{tabular}{" + "|".join(["c"] * len(headers)) + "}\n"
    latex_table += "\\hline\n"
    
    # Add headers
    latex_table += " & ".join(headers) + " \\\\\n"
    latex_table += "\\hline\n"
    
    # Add rows
    for row in rows:
        latex_table += " & ".join(row) + " \\\\\n"
        latex_table += "\\hline\n"
    
    # End the table
    latex_table += "\\end{tabular}"
    
    return latex_table





def find_easy_edit_metric_files(root_dir):
    metric_files = []
    for dirpath, dirnames, filenames in os.walk(root_dir):
        for file in filenames:
            if file == "post_edit_easy_edit_metrics.json":
                metric_files.append(os.path.join(dirpath, file))
    return metric_files





def find_sentiment_labels_metric_files(root_dir):
    metric_files = []
    for dirpath, dirnames, filenames in os.walk(root_dir):
        for file in filenames:
            if file == "edit_effect_sentiment_labels_metric.json":
                metric_files.append(os.path.join(dirpath, file))
    return metric_files



def find_sentiment_scores_metric_files(root_dir):
    metric_files = []
    for dirpath, dirnames, filenames in os.walk(root_dir):
        for file in filenames:
            if file == "edit_effect_sentiment_scores_metric.json":
                metric_files.append(os.path.join(dirpath, file))
    return metric_files





def find_kl_div_metric_files(root_dir):
    metric_files = []
    for dirpath, dirnames, filenames in os.walk(root_dir):
        for file in filenames:
            if file == "edit_effect_kl_div_metric.json":
                metric_files.append(os.path.join(dirpath, file))
    return metric_files





def find_perplexity_metric_files(root_dir):
    metric_files = []
    for dirpath, dirnames, filenames in os.walk(root_dir):
        for file in filenames:
            if file == "edit_effect_perplexity_metric.json":
                metric_files.append(os.path.join(dirpath, file))
    return metric_files






def change_list_format(metric_files):
    
    new_metric_dict = {}
    
    for metric_file in metric_files:
        
        metric_file_config = metric_file[metric_file.find("outputs") + len("outputs\\"):].split("\\")
        editing_method = metric_file_config[0]
        model_name = metric_file_config[1]
        decoding_strategy = metric_file_config[2]
        number_of_sequential_edits = int(metric_file_config[3].split("_")[0])
        time_stamp = metric_file_config[4]
        metric_file_name = metric_file_config[5]
        
        new_metric_dict.update({metric_file : {"editing_method" : editing_method, "model_name" : model_name, "decoding_strategy" : decoding_strategy, "number_of_sequential_edits" : number_of_sequential_edits, "time_stamp" : time_stamp, "metric_file_name" : metric_file_name}})

    return new_metric_dict







def extract_kl_div_values(metric_path):
    
    metric_file = read_json_from_file(metric_path)
        
    kl_div_locality_neighborhood = metric_file["kl_div_locality_neighborhood"]
    kl_div_locality_distracting = metric_file["kl_div_locality_distracting"]
    

    edits_locality_neighborhood = [edit_item for edit_item in kl_div_locality_neighborhood]    
    edits_locality_distracting = [edit_item for edit_item in kl_div_locality_distracting] 
    
    
    edit_averages_locality_neighborhood_first_token = [] 
    edit_averages_locality_neighborhood_differing_token = [] 
    
    for edit in edits_locality_neighborhood:
        current_edit_average_first_token = statistics.mean([seq["kl_div_first_token"] for seq in edit])
        current_edit_average_differing_token = statistics.mean([seq["kl_div_differing_token"] for seq in edit])
        edit_averages_locality_neighborhood_first_token.append(current_edit_average_first_token)
        edit_averages_locality_neighborhood_differing_token.append(current_edit_average_differing_token)
        

    all_edits_average_locality_neighborhood_first_token = statistics.mean(edit_averages_locality_neighborhood_first_token)
    all_edits_average_locality_neighborhood_differing_token = statistics.mean(edit_averages_locality_neighborhood_differing_token)
    
    
    edit_averages_locality_distracting_first_token = [] 
    edit_averages_locality_distracting_differing_token = [] 
    
    for edit in edits_locality_distracting:
        current_edit_average_first_token = statistics.mean([seq["kl_div_first_token"] for seq in edit])
        current_edit_average_differing_token = statistics.mean([seq["kl_div_differing_token"] for seq in edit])
        edit_averages_locality_distracting_first_token.append(current_edit_average_first_token)
        edit_averages_locality_distracting_differing_token.append(current_edit_average_differing_token)
        

    all_edits_average_locality_distracting_first_token = statistics.mean(edit_averages_locality_distracting_first_token)
    all_edits_average_locality_distracting_differing_token = statistics.mean(edit_averages_locality_distracting_differing_token)
    
    
    kl_div_dict = {
        "kl_div_neighborhood_first_token_average" : all_edits_average_locality_neighborhood_first_token,
        "kl_div_neighborhood_differing_token_average" : all_edits_average_locality_neighborhood_differing_token,
        "kl_div_distracting_first_token_average" : all_edits_average_locality_distracting_first_token,
        "kl_div_distracting_differing_token_average" : all_edits_average_locality_distracting_differing_token, 
    }
    
    
        
    return kl_div_dict





def extract_perplexity_values(metric_path):
    metric_file = read_json_from_file(metric_path)
    abs_edits_locality_neighborhood = [item["absolute_locality_neighborhood_perplexity"] for item in metric_file]
    abs_edits_locality_distracting = [item["absolute_locality_distracting_perplexity"] for item in metric_file]
    rel_edits_locality_neighborhood = [item["relative_locality_neighborhood_perplexity"] for item in metric_file]
    rel_edits_locality_distracting = [item["relative_locality_distracting_perplexity"] for item in metric_file]

    def extract_last_list(s):
        pattern = r"\[([-]?\d*\.?\d+(?:\s*,\s*[-]?\d*\.?\d+)*)\]$"
        match = re.search(pattern, s)

        if match:
            result = [float(x) for x in match.group(1).split(',')]
            return result


    abs_edits_locality_neighborhood = [extract_last_list(item) for item in abs_edits_locality_neighborhood]
    abs_edits_locality_neighborhood_average = statistics.mean([statistics.mean(lst) for lst in abs_edits_locality_neighborhood])
    
    abs_edits_locality_distracting = [extract_last_list(item) for item in abs_edits_locality_distracting]
    abs_edits_locality_distracting_average = statistics.mean([statistics.mean(lst) for lst in abs_edits_locality_distracting])
    
    rel_edits_locality_neighborhood = [extract_last_list(item) for item in rel_edits_locality_neighborhood]
    rel_edits_locality_neighborhood_average = statistics.mean([statistics.mean(lst) for lst in rel_edits_locality_neighborhood])
    
    rel_edits_locality_distracting = [extract_last_list(item) for item in rel_edits_locality_distracting]
    rel_edits_locality_distracting_average = statistics.mean([statistics.mean(lst) for lst in rel_edits_locality_distracting])
    
    
    perplexity_dict = {
        "absolute_perplexity_neighborhood_average" : abs_edits_locality_neighborhood_average,
        "absolute_perplexity_distracting_average" : abs_edits_locality_distracting_average,
        "relative_perplexity_neighborhood_average" : rel_edits_locality_neighborhood_average,
        "relative_perplexity_distracting_average" : rel_edits_locality_distracting_average,
    }
    
    return perplexity_dict






def extract_sentiment_labels_values(metric_path):
    metric_file = read_json_from_file(metric_path)
    
    keys = ["prompt","light_generality_1","light_generality_2","light_generality_3","strong_generality","portability_synonym","portability_one_hop","portability_two_hop","locality_neighborhood","locality_distracting"]
    
    edits = {}
    edits_averages = {}
    
    for key in keys:
        edits[key] = [item[key] for item in metric_file]


    def extract_last_list(s):
        pattern = r"\[([0-9\.\s,]+)\]$"
        match = re.search(pattern, s)

        if match:
            result = [float(x) for x in match.group(1).split(',')]
            return result
        
        

    for key in keys:
        edits[key] = [extract_last_list(item) for item in edits[key]]
        edits_averages[key] = statistics.mean([statistics.mean(lst) for lst in edits[key]])
    
    
    sentiment_dict = {}
    
    for key in keys:
        sentiment_dict[f"sentiment_label_{key}_average"] = edits_averages[key]
    
    
    return sentiment_dict






def extract_sentiment_scores_values(metric_path):
    metric_file = read_json_from_file(metric_path)
    
    keys = ["prompt","light_generality_1","light_generality_2","light_generality_3","strong_generality","portability_synonym","portability_one_hop","portability_two_hop","locality_neighborhood","locality_distracting"]
    
    edits = {}
    edits_averages = {}
    
    for key in keys:
        edits[key] = [item[key] for item in metric_file]


    
    def extract_last_list(s):
        end_idx = s.rfind(']')
        if end_idx == -1:
            return None
        
        start_idx = s.rfind('[', 0, end_idx)
        if start_idx == -1:
            return None
        
        list_str = s[start_idx + 1:end_idx]
        
        try:
            result = [float(x.strip()) for x in list_str.split(',')]
            return result
        except ValueError:
            return None
        
        

    for key in keys:
        edits[key] = [extract_last_list(item) for item in edits[key]]
        edits_averages[key] = statistics.mean([statistics.mean(lst) for lst in edits[key]])
    
    
    sentiment_dict = {}
    
    for key in keys:
        sentiment_dict[f"sentiment_score_{key}_average"] = edits_averages[key]
    
    
    return sentiment_dict











def format_kl_div_as_row(metric_configuration, metric_value):
    
    return [
        str.upper(metric_configuration["model_name"]),
        metric_configuration["editing_method"],
        f'{metric_value["kl_div_neighborhood_first_token_average"]:.{precision}f}',
        f'{metric_value["kl_div_neighborhood_differing_token_average"]:.{precision}f}',
        f'{metric_value["kl_div_distracting_first_token_average"]:.{precision}f}',
        f'{metric_value["kl_div_distracting_differing_token_average"]:.{precision}f}'
    ]




def format_perplexity_as_row(metric_configuration, metric_value):
    return [
        str.upper(metric_configuration["model_name"]),
        metric_configuration["editing_method"],
        f'{metric_value["absolute_perplexity_neighborhood_average"]:.{precision}f}',
        f'{metric_value["relative_perplexity_neighborhood_average"]:.{precision}f}',
        f'{metric_value["absolute_perplexity_distracting_average"]:.{precision}f}',
        f'{metric_value["relative_perplexity_distracting_average"]:.{precision}f}'
    ]






def format_sentiment_labels_as_row(metric_configuration, metric_value):
    
    light_generality = statistics.mean([metric_value["sentiment_label_light_generality_1_average"], metric_value["sentiment_label_light_generality_2_average"], metric_value["sentiment_label_light_generality_3_average"]])
    score = calculate_score([metric_value["sentiment_label_prompt_average"],
                            light_generality, metric_value["sentiment_label_strong_generality_average"],
                            metric_value["sentiment_label_portability_synonym_average"],
                            metric_value["sentiment_label_portability_one_hop_average"],
                            metric_value["sentiment_label_portability_two_hop_average"]])
    
    return [
        str.upper(metric_configuration["model_name"]),
        metric_configuration["editing_method"],
        f'{score:.{precision}f}',
        f'{metric_value["sentiment_label_prompt_average"]:.{precision}f}',
        f'{light_generality:.{precision}f}',
        f'{metric_value["sentiment_label_strong_generality_average"]:.{precision}f}',
        f'{metric_value["sentiment_label_portability_synonym_average"]:.{precision}f}',
        f'{metric_value["sentiment_label_portability_one_hop_average"]:.{precision}f}',
        f'{metric_value["sentiment_label_portability_two_hop_average"]:.{precision}f}',
        f'{metric_value["sentiment_label_locality_neighborhood_average"]:.{precision}f}',
        f'{metric_value["sentiment_label_locality_distracting_average"]:.{precision}f}'
    ]






def format_sentiment_scores_as_row(metric_configuration, metric_value):
    
    light_generality = statistics.mean([metric_value["sentiment_score_light_generality_1_average"], metric_value["sentiment_score_light_generality_2_average"], metric_value["sentiment_score_light_generality_3_average"]])
    
    return [
        str.upper(metric_configuration["model_name"]),
        metric_configuration["editing_method"],
        f'{metric_value["sentiment_score_prompt_average"]:.{precision}f}',
        f'{light_generality:.{precision}f}',
        f'{metric_value["sentiment_score_strong_generality_average"]:.{precision}f}',
        f'{metric_value["sentiment_score_portability_synonym_average"]:.{precision}f}',
        f'{metric_value["sentiment_score_portability_one_hop_average"]:.{precision}f}',
        f'{metric_value["sentiment_score_portability_two_hop_average"]:.{precision}f}',
        f'{metric_value["sentiment_score_locality_neighborhood_average"]:.{precision}f}',
        f'{metric_value["sentiment_score_locality_distracting_average"]:.{precision}f}'
    ]





def change_underscore(s):
    return "-".join(s.split("_"))






def reduce_rows_to_averages(rows):
    grouped = defaultdict(list)

    # Group rows by (model, editing method)
    for row in rows:
        key = (row[0], row[1])  # First two columns (model, editing method)
        values = list(map(float, row[2:])) 
        grouped[key].append(values)

    # Average all columns for each (model, editing method) group
    reduced_rows = []
    for key, value_lists in grouped.items():
        # Transpose the list of lists to group by column
        columns = list(zip(*value_lists))
        # Compute the average for each column
        averages = [round(statistics.mean(column), precision) for column in columns]
        reduced_rows.append(list(key) + averages)

    return reduced_rows






def filter_dict_by(dictionary, conditions):
    
    filtered_dict = {
        key: value for key, value in dictionary.items()
        if all(value.get(k) == v for k, v in conditions.items())
    }


    return filtered_dict




def filter_by(conditions):
    global kl_div_files_dict, sentiment_labels_files_dict, sentiment_scores_files_dict, perplexity_files_dict, headers

    kl_div_files_dict = filter_dict_by(kl_div_files_dict, conditions)
    sentiment_labels_files_dict = filter_dict_by(sentiment_labels_files_dict, conditions)
    sentiment_scores_files_dict = filter_dict_by(sentiment_scores_files_dict, conditions)
    perplexity_files_dict = filter_dict_by(perplexity_files_dict, conditions)







def generate_kl_div_table(rows):
    # Define the LaTeX table header
    latex_table = r"""
    \begin{table}[h]
    \centering
    \small % Reduce font size to fit the table if needed
    \resizebox{\textwidth}{!}{ % Scale the table to fit the page width if necessary
    \begin{tabular}{l cc cc}
    \toprule
    \multirow{3}{*}{\textbf{Editor}} & \multicolumn{4}{c}{\textbf{Locality} $\downarrow$} \\
    \cmidrule(lr){2-5}
    & \multicolumn{2}{c}{\textbf{Neighborhood}} & \multicolumn{2}{c}{\textbf{Distracting}} \\
    \cmidrule(lr){2-3} \cmidrule(lr){4-5}
    & First Token & Differing Token & First Token & Differing Token \\
    \midrule
    """

    # Keep track of the current model to group rows by model
    current_model = None

    # Iterate through each row in the input data
    for row in rows:
        model_name = row[0]  # First column is the model name
        editor = row[1]      # Second column is the editor
        metrics = row[2:]    # Remaining columns are the metric values (4 values)

        # If the model changes, add a model header (left-aligned)
        if model_name != current_model:
            if current_model is not None:  # Add a midrule before the new model (except for the first model)
                latex_table += r"\midrule" + "\n"
            latex_table += r"\multicolumn{5}{l}{" + model_name + r"} \\" + "\n"
            latex_table += r"\midrule" + "\n"
            current_model = model_name

        # Add the row for the editor and its metrics
        metrics_str = " & ".join(map(str, metrics))  # Convert metrics to strings and join with " & "
        latex_table += f"{editor} & {metrics_str} \\\\\n"

    # Close the table
    latex_table += r"""\bottomrule
    \end{tabular}
    }
    \caption{Performance metrics for different editors across models.}
    \label{tab:performance_metrics}
    \end{table}
    """

    return latex_table









def generate_perplexity_table(rows):
    
    r'''
    \begin{table}[h]
    \centering
    \small % Reduce font size to fit the table if needed
    \resizebox{\textwidth}{!}{ % Scale the table to fit the page width if necessary
    \begin{tabular}{l cc cc}
    \toprule
    \multirow{3}{*}{\textbf{Editor}} & \multicolumn{4}{c}{\textbf{Locality} $\downarrow$} \\
    \cmidrule(lr){2-5}
    & \multicolumn{2}{c}{\textbf{Neighborhood}} & \multicolumn{2}{c}{\textbf{Distracting}} \\
    \cmidrule(lr){2-3} \cmidrule(lr){4-5}
    & Absolute & Relative & Absolute & Relative \\
    \midrule
    \multicolumn{5}{l}{gpt2-xl} \\
    \midrule
    MEND & 0.0 & 0.0 & 0.0 & 0.0 \\
    \midrule
    \multicolumn{5}{l}{GPT-J} \\
    \midrule
    FT & 25.5 & 100.0 & 99.9 & 96.6 \\
    \bottomrule
    \end{tabular}
    }
    \caption{Performance metrics for different editors across models.}
    \label{tab:performance_metrics}
    \end{table}
    
    '''
    
    
    # Define the LaTeX table header
    latex_table = r"""
    \begin{table}[h]
    \centering
    \small % Reduce font size to fit the table if needed
    \resizebox{\textwidth}{!}{ % Scale the table to fit the page width if necessary
    \begin{tabular}{l cc cc}
    \toprule
    \multirow{3}{*}{\textbf{Editor}} & \multicolumn{4}{c}{\textbf{Locality} $\downarrow$} \\
    \cmidrule(lr){2-5}
    & \multicolumn{2}{c}{\textbf{Neighborhood}} & \multicolumn{2}{c}{\textbf{Distracting}} \\
    \cmidrule(lr){2-3} \cmidrule(lr){4-5}
    & Absolute & Relative & Absolute & Relative \\
    \midrule
    """

    # Keep track of the current model to group rows by model
    current_model = None

    # Iterate through each row in the input data
    for row in rows:
        model_name = row[0]  # First column is the model name
        editor = row[1]      # Second column is the editor
        metrics = row[2:]    # Remaining columns are the metric values (4 values)

        # If the model changes, add a model header (left-aligned)
        if model_name != current_model:
            if current_model is not None:  # Add a midrule before the new model (except for the first model)
                latex_table += r"\midrule" + "\n"
            latex_table += r"\multicolumn{5}{l}{" + model_name + r"} \\" + "\n"
            latex_table += r"\midrule" + "\n"
            current_model = model_name

        # Add the row for the editor and its metrics
        metrics_str = " & ".join(map(str, metrics))  # Convert metrics to strings and join with " & "
        latex_table += f"{editor} & {metrics_str} \\\\\n"

    # Close the table
    latex_table += r"""\bottomrule
    \end{tabular}
    }
    \caption{Performance metrics for different editors across models.}
    \label{tab:performance_metrics}
    \end{table}
    """

    return latex_table













def generate_sentiment_table(rows):
    r'''
    \begin{table}[h]
    \centering
    \small % Reduce font size to fit the table if needed
    \resizebox{\textwidth}{!}{ % Scale the table to fit the page width if necessary
    \begin{tabular}{l c cc ccc cc}
    \toprule
    \multirow{2}{*}{\textbf{Editor}} & \multicolumn{1}{c}{\textbf{Reliability } $\uparrow$} & \multicolumn{2}{c}{\textbf{Generalization} $\uparrow$} & \multicolumn{3}{c}{\textbf{Portability} $\uparrow$} & \multicolumn{2}{c}{\textbf{Locality} $\downarrow$} \\
    \cmidrule(lr){2-2} \cmidrule(lr){3-4} \cmidrule(lr){5-7} \cmidrule(lr){8-9}
    & Prompt & Light & Significant & Synonym & One-hop & Two-hop &  Neighborhood & Distracting \\
    \midrule
    \multicolumn{9}{l}{GPT-2 XL} \\
    \midrule
    MEND & 65.1 & 100.0 & 98.8 & 87.9 & 46.6 & 2 & 1 & 3\\
    \midrule
    \multicolumn{9}{l}{GPT-J} \\
    \midrule
    FT & 25.5 & 100.0 & 99.9 & 96.6  & 71.0 & 2 & 1 & 3\\
    \bottomrule
    \end{tabular}
    }
    \caption{Performance metrics for different editors across GPT-2 XL and GPT-J models, with standard deviations in parentheses.}
    \label{tab:performance_metrics}
    \end{table}
    '''
    


    # Define the LaTeX table header
    latex_table = r"""
    \begin{table}[h]
    \centering
    \small % Reduce font size to fit the table if needed
    \resizebox{\textwidth}{!}{ % Scale the table to fit the page width if necessary
    \begin{tabular}{l c cc ccc cc}
    \toprule
    \multirow{2}{*}{\textbf{Editor}} & \multicolumn{1}{c}{\textbf{Reliability} $\uparrow$} & \multicolumn{2}{c}{\textbf{Generalization} $\uparrow$} & \multicolumn{3}{c}{\textbf{Portability} $\uparrow$} & \multicolumn{2}{c}{\textbf{Locality} $\downarrow$} \\
    \cmidrule(lr){2-2} \cmidrule(lr){3-4} \cmidrule(lr){5-7} \cmidrule(lr){8-9}
    & Prompt & Light & Significant & Synonym & One-hop & Two-hop & Neighborhood & Distracting \\
    \midrule
    """

    # Keep track of the current model to group rows by model
    current_model = None

    # Iterate through each row in the input data
    for row in rows:
        model_name = row[0]  # First column is the model name
        editor = row[1]      # Second column is the editor
        metrics = row[2:]    # Remaining columns are the metric values

        # If the model changes, add a model header (left-aligned)
        if model_name != current_model:
            if current_model is not None:  # Add a midrule before the new model (except for the first model)
                latex_table += r"\midrule" + "\n"
            latex_table += r"\multicolumn{9}{l}{" + model_name + r"} \\" + "\n"
            latex_table += r"\midrule" + "\n"
            current_model = model_name

        # Add the row for the editor and its metrics
        metrics_str = " & ".join(map(str, metrics))  # Convert metrics to strings and join with " & "
        latex_table += f"{editor} & {metrics_str} \\\\\n"

    # Close the table
    latex_table += r"""\bottomrule
    \end{tabular}
    }
    \caption{Performance metrics for different editors across models.}
    \label{tab:performance_metrics}
    \end{table}
    """

    return latex_table











def generate_sentiment_table_with_scores(labels_rows, scores_rows):
    # Define the LaTeX table header with Score column
    latex_table = r"""
    \begin{table}[h]
    \centering
    \small
    \resizebox{\textwidth}{!}{
    \begin{tabular}{l c cc cccc cccccc cccc}
    \toprule
    \multirow{3}{*}{\textbf{Editor}} & \multirow{3}{*}{\textbf{Score}} & \multicolumn{2}{c}{\textbf{Reliability} $\uparrow$} & \multicolumn{4}{c}{\textbf{Generalization} $\uparrow$} & \multicolumn{6}{c}{\textbf{Portability} $\uparrow$} & \multicolumn{4}{c}{\textbf{Locality} $\downarrow$} \\ 
    \cmidrule(lr){3-4} \cmidrule(lr){5-8} \cmidrule(lr){9-14} \cmidrule(lr){15-18}
    & & \multicolumn{2}{c}{Prompt} & \multicolumn{2}{c}{Light} & \multicolumn{2}{c}{Significant} & \multicolumn{2}{c}{Synonym} & \multicolumn{2}{c}{One-hop} & \multicolumn{2}{c}{Two-hop} & \multicolumn{2}{c}{Neighborhood} & \multicolumn{2}{c}{Distracting} \\  
    \cmidrule(lr){3-4} \cmidrule(lr){5-6} \cmidrule(lr){7-8} \cmidrule(lr){9-10} \cmidrule(lr){11-12} \cmidrule(lr){13-14} \cmidrule(lr){15-16} \cmidrule(lr){17-18}
    & & PS & NS & PS & NS & PS & NS & PS & NS & PS & NS & PS & NS & PS & NS & PS & NS \\  
    \midrule
    """

    # Track the current model
    current_model = None

    for ps_row, ns_row in zip(labels_rows, scores_rows):
        model_name_ps = ps_row[0]  # First column is the model name from PS
        editor_ps = ps_row[1]      # Second column is the editor from PS
        score_ps = ps_row[2]       # Third column is the Score from PS
        ps_metrics = ps_row[3:]    # Metrics start from 4th column (index 3)
        ns_metrics = ns_row[2:]    # NS metrics start from 3rd column (after model and editor)

        # Verify model names match between PS and NS rows
        if model_name_ps != ns_row[0]:
            raise ValueError("Model names in PS and NS rows must match")

        # If the model changes, add a model header
        if model_name_ps != current_model:
            if current_model is not None:  # Add a midrule before new model (except first)
                latex_table += r"\midrule" + "\n"
            latex_table += r"\multicolumn{18}{l}{\textbf{" + model_name_ps + r"}} \\" + "\n"
            latex_table += r"\midrule" + "\n"
            current_model = model_name_ps

        # Interleave PS and NS metrics
        combined_metrics = []
        for ps_val, ns_val in zip(ps_metrics, ns_metrics):
            combined_metrics.extend([ps_val, ns_val])

        # Add the row with Score and interleaved metrics
        metrics_str = " & ".join(map(str, combined_metrics))
        latex_table += f"{editor_ps} & {score_ps} & {metrics_str} \\\\\n"

    # Close the table
    latex_table += r"""\bottomrule
    \end{tabular}
    }
    \caption{Performance metrics for different editors across models, with PS and NS scores.}
    \label{tab:performance_metrics}
    \end{table}
    """

    return latex_table






# Caclulates the harmonic mean
def calculate_score(args):
    return statistics.mean(args)
    # return statistics.harmonic_mean(args)
        







if __name__ == "__main__":
    
    # Calculate harmonic mean of all metrics you want as final score in seperate table
    
    
    kl_div_files_dict = change_list_format(find_kl_div_metric_files(os.getcwd()))
    sentiment_labels_files_dict = change_list_format(find_sentiment_labels_metric_files(os.getcwd()))
    sentiment_scores_files_dict = change_list_format(find_sentiment_scores_metric_files(os.getcwd()))
    perplexity_files_dict = change_list_format(find_perplexity_metric_files(os.getcwd()))
    
    kl_div_rows = []
    perplexity_rows = []
    sentiment_labels_rows = []
    sentiment_scores_rows = []

    
    filter_conditions = {
        # "editing_method" : "MEND",
        # "model_name" : "gpt2-xl",
        "decoding_strategy" : "beam-search multinomial sampling",
        "number_of_sequential_edits" : 1
    }
    
    
    if len(filter_conditions) > 0:
        filter_by(filter_conditions)
    
    

    for metric_path, metric_configuration in sentiment_labels_files_dict.items():
        result = extract_sentiment_labels_values(metric_path)
        sentiment_labels_rows.append(format_sentiment_labels_as_row(metric_configuration, result))
        
        
    for metric_path, metric_configuration in sentiment_scores_files_dict.items():
        result = extract_sentiment_scores_values(metric_path)
        sentiment_scores_rows.append(format_sentiment_scores_as_row(metric_configuration, result))
    
    
    for metric_path, metric_configuration in kl_div_files_dict.items():
        result = extract_kl_div_values(metric_path)
        kl_div_rows.append(format_kl_div_as_row(metric_configuration, result))
    
    
    for metric_path, metric_configuration in perplexity_files_dict.items():
        result = extract_perplexity_values(metric_path)
        perplexity_rows.append(format_perplexity_as_row(metric_configuration, result))
    
    
    
    sentiment_labels_rows = reduce_rows_to_averages(sentiment_labels_rows)
    sentiment_scores_rows = reduce_rows_to_averages(sentiment_scores_rows)
    kl_div_rows = reduce_rows_to_averages(kl_div_rows)
    perplexity_rows = reduce_rows_to_averages(perplexity_rows)
    
    
    full_sentiment_table = generate_sentiment_table_with_scores(sentiment_labels_rows, sentiment_scores_rows)
    sentiment_labels_table = generate_sentiment_table(sentiment_labels_rows)
    kl_div_table = generate_kl_div_table(kl_div_rows)
    perplexity_table = generate_perplexity_table(perplexity_rows)
    
    
    # print(full_sentiment_table)
    # print(sentiment_labels_table)
    # print(kl_div_table)
    print(perplexity_table)
    
