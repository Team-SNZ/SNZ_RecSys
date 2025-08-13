import pandas as pd
import torch
from sentence_transformers import SentenceTransformer, InputExample, losses
from torch.utils.data import DataLoader
import os

try:
    profiles_df = pd.read_csv("./User_100.csv", encoding='utf-8-sig')
    feedback_df = pd.read_csv("./synthetic_feedback_data.csv", encoding='utf-8-sig')
    print("'User_100.csv' and 'synthetic_feedback_data.csv' are loaded")
except FileNotFoundError as e:
    print(f"Error: {e.filename} file not found")
    print("Please run 'generate_feedback_csv.py' first to create 'synthetic_feedback_data.csv'")
    exit()

# data preprocessing and training example generation
profile_map = profiles_df.set_index('ID')['Profile'].to_dict()
train_examples = []

for _, row in feedback_df.iterrows():
    profile_a = profile_map.get(row['user_id_A'])
    profile_b = profile_map.get(row['user_id_B'])

    if profile_a and profile_b:
        # normalize score (1~5 -> 0.0~1.0)
        normalized_score = (row['score'] - 1) / 4.0
        train_examples.append(InputExample(texts=[profile_a, profile_b], label=normalized_score))

print(f"{len(train_examples)} number of training data is ready")

# train
print("\nmodel and loss function is defined")

model_name = 'jhgan/ko-sbert-sts'  
model = SentenceTransformer(model_name)
train_loss = losses.CosineSimilarityLoss(model=model)
print(f"pretrained model: '{model_name}'")
print("loss function: ContrastiveLoss")

epochs = 1
batch_size=16
warmup_steps = int(len(train_examples) / batch_size * 0.1)
finetuned_model_path = './finetuned_feedback_model'

train_dataloader = DataLoader(train_examples, shuffle=True, batch_size=batch_size)

print(f"\nmodel training started... (Epochs: {epochs}, Batch Size: {batch_size})")

model.fit(train_objectives=[(train_dataloader, train_loss)],
          epochs=epochs,
          warmup_steps=warmup_steps,
          output_path=finetuned_model_path,
          show_progress_bar=True)

print(f"\nmodel training completed! improved model is saved in '{finetuned_model_path}'")



finetuned_model = SentenceTransformer(finetuned_model_path)

# Test
test_user_id = 1
query_profile = profile_map.get(test_user_id)

if query_profile:
    candidate_user_ids = list(profile_map.keys())
    candidate_profiles = list(profile_map.values())

    query_embedding = finetuned_model.encode(query_profile, convert_to_tensor=True)
    candidate_embeddings = finetuned_model.encode(candidate_profiles, convert_to_tensor=True)

    from sentence_transformers import util
    cosine_scores = util.cos_sim(query_embedding, candidate_embeddings)[0]

    results = []
    for uid, score in zip(candidate_user_ids, cosine_scores):
        if uid != test_user_id:
            results.append({"user_id": uid, "similarity_score": score.item()})

    results_df = pd.DataFrame(results).sort_values(by='similarity_score', ascending=False)

    print(f"[Test] similarity between user_id={test_user_id} and other users (top 10):")
    print(f"  - reference profile: '{query_profile[:40]}...'")
    print(results_df.head(10).to_string(index=False))

    # check positive partners from generated feedback data
    positive_partners = feedback_df[(feedback_df['user_id_A'] == test_user_id) & (feedback_df['score'] >= 4)]
    print(f"\n  - reference: positive partners from generated feedback data")
    print(positive_partners[['user_id_B', 'score']].to_string(index=False))
else:
    print(f"profile of user_id {test_user_id} is not found")
