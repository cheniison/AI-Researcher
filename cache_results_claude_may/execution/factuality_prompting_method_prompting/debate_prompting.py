from openai import OpenAI
import anthropic
import json
import random 
from tqdm import tqdm 
from utils import call_api, load_model
import random
random.seed(2024)

## Step 1: Generate synthetic test examples
def generate_testset():
    test_data = [
        {
            "input": "The Eiffel Tower is the tallest building in Paris.",
            "output": "REFUTES"
        },
        {
            "input": "The Great Wall of China is visible from space.",
            "output": "REFUTES"
        },
        {
            "input": "The capital of Australia is Sydney.",
            "output": "REFUTES"
        },
        {
            "input": "The Earth is the third planet from the Sun.",
            "output": "SUPPORTS"
        },
        {
            "input": "The Mona Lisa was painted by Leonardo da Vinci.",
            "output": "SUPPORTS"
        }
    ]

    return test_data


## Step 2: Implement the baseline method 
def baseline_method(client, model_name, seed, question):
    ## self-consistency scoring
    prompt = "Given the following statement: {}\n".format(question)
    prompt += "Please verify the factual accuracy of the statement. Provide a score from 1 to 5, where 1 means the statement is completely inaccurate and 5 means the statement is completely accurate. Explain your reasoning."
    prompt_messages = [{"role": "user", "content": prompt}]
    response, _ = call_api(client, model_name, prompt_messages, temperature=0., max_tokens=2000, seed=seed, json_output=False)
    return response.strip()


## Step 3: Implement the proposed method 
def proposed_method(client, model_name, seed, question, print_all=False):
    intermediate_outputs = "" 
    
    if print_all:
        print ("question:\n", question)

    ## debate round 1: initial statement
    prompt = "Consider the following statement: {}\n".format(question)
    prompt += "Please provide your perspective on the accuracy of this statement."
    prompt_messages = [{"role": "user", "content": prompt}]
    model_a_output, _ = call_api(client, model_name, prompt_messages, temperature=0., max_tokens=2000, seed=seed, json_output=False)
    intermediate_outputs += "Model A's Initial Statement:\n" + model_a_output + "\n\n"
    if print_all:
        print ("Model A's Initial Statement:\n", model_a_output)

    ## debate round 2: critique
    prompt = "Consider the following statement: {}\n".format(model_a_output)
    prompt += "Please identify any factual inaccuracies or inconsistencies in the statement. Provide evidence to support your arguments."
    prompt_messages = [{"role": "user", "content": prompt}]
    model_b_output, _ = call_api(client, model_name, prompt_messages, temperature=0., max_tokens=2000, seed=seed, json_output=False)
    intermediate_outputs += "Model B's Critique:\n" + model_b_output + "\n\n"
    if print_all:
        print ("Model B's Critique:\n", model_b_output)

    ## debate round 3: rebuttal
    prompt = "Consider the following critique: {}\n".format(model_b_output)
    prompt += "Please defend the factual accuracy of your original statement in light of these counterarguments. Provide evidence to support your defense."
    prompt_messages = [{"role": "user", "content": prompt}]
    model_a_rebuttal, _ = call_api(client, model_name, prompt_messages, temperature=0., max_tokens=2000, seed=seed, json_output=False)
    intermediate_outputs += "Model A's Rebuttal:\n" + model_a_rebuttal + "\n\n"
    if print_all:
        print ("Model A's Rebuttal:\n", model_a_rebuttal)

    ## debate outcome
    prompt = "Given the following debate:\n\nInitial Statement: {}\nCritique: {}\nRebuttal: {}\n\n".format(model_a_output, model_b_output, model_a_rebuttal)
    prompt += "Please provide a final verdict on whether the original statement is SUPPORTED or REFUTED based on the arguments presented in the debate."
    prompt_messages = [{"role": "user", "content": prompt}]
    debate_outcome, _ = call_api(client, model_name, prompt_messages, temperature=0., max_tokens=2000, seed=seed, json_output=False)
    intermediate_outputs += "Debate Outcome:\n" + debate_outcome
    if print_all:
        print ("Debate Outcome:\n", debate_outcome)

    return debate_outcome.strip(), intermediate_outputs


## Step 4: Define the style evaluator
def style_evaluator(client, model_name, seed, question, baseline_prediction, proposed_prediction):
    prompt = "Given the task: {}\n".format(question)
    prompt += "The baseline method produced the following output:\n{}\n\n".format(baseline_prediction)
    prompt += "The proposed new method produced the following output:\n{}\n\n".format(proposed_prediction)
    prompt += "Now determine if the proposed method is better by checking if it has satisfied the following criteria:\n"
    prompt += "1. The proposed method's output should include all the key debate components: initial statement, critique, rebuttal, and final outcome.\n"
    prompt += "2. The proposed method should provide a more comprehensive analysis of the statement's accuracy compared to the baseline method.\n"
    prompt += "Just tell me 'yes' or 'no' for whether the criteria are met, nothing else is needed."
    prompt_messages = [{"role": "user", "content": prompt}]
    response, _ = call_api(client, model_name, prompt_messages, temperature=0., max_tokens=1, seed=seed, json_output=False)
    
    judgment = False
    if response.strip().lower() == "yes":
        return True 
    
    return judgment


## Step 5: Define the output evaluator
def output_evaluator(client, model_name, seed, question, gold_label, prediction):
    prompt = "Given the following statement and the debate outcome, determine if the debate outcome is correct. Just tell me 'yes' or 'no', nothing else is needed.\n\nStatement: {}\n\nDebate Outcome: {}\n\nGround Truth: {}\n\n".format(question, prediction, gold_label)
    prompt_messages = [{"role": "user", "content": prompt}]
    response, _ = call_api(client, model_name, prompt_messages, temperature=0., max_tokens=1, seed=seed, json_output=False)
    
    judgment = False
    if response.strip().lower() == "yes":
        return True 
    
    return judgment


## Step 6: Define the function that runs the experiments to obtain model predictions and performance
## you shouldn't need to modify this function in most cases
def run_experiment(client, model_name, seed, testset):
    sample_size = len(testset) 
    baseline_predictions = []
    proposed_predictions = []

    baseline_correctness = []
    proposed_correctness = []

    style_check = []

    for i in tqdm(range(sample_size)):
        question = testset[i]["input"].strip()
        gold_label = testset[i]["output"].strip()
        
        baseline_prediction = baseline_method(client, model_name, seed, question)
        proposed_prediction_final, proposed_prediction_intermediate = proposed_method(client, model_name, seed, question)
        baseline_predictions.append(baseline_prediction)
        proposed_predictions.append(proposed_prediction_final)
        
        baseline_correctness.append(output_evaluator(client, model_name, seed, question, gold_label, baseline_prediction))
        proposed_correctness.append(output_evaluator(client, model_name, seed, question, gold_label, proposed_prediction_final))

        style_check.append(style_evaluator(client, model_name, seed, question, baseline_prediction, proposed_prediction_intermediate))

    return baseline_correctness, proposed_correctness, style_check


## Step 7: Execute the experiments and compare performance 
if __name__ == "__main__":
    testset = generate_testset()
    print ("simulated {} test examples for evaluation.".format(len(testset)))

    model_name = "claude-3-opus-20240229" ## don't change this
    seed = 2024 
    client = load_model(model_name)
    print ("using model: ", model_name)

    ## output correctness 
    baseline_correctness, proposed_correctness, style_check = run_experiment(client, model_name, seed, testset)
    print ("baseline correctness: ", sum(baseline_correctness) / len(baseline_correctness))
    print ("proposed correctness: ", sum(proposed_correctness) / len(proposed_correctness))
    print ("style check pass rate: ", sum(style_check) / len(style_check))
