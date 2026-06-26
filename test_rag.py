import sys
from apps.backend.src.agent.portrai_cms_agent import portrai_agent

query = "bagaimana cara agar participant mendapatkan email untuk mengerjakan portrai?"
print(f"Query: {query}")
portrai_agent._initialize()

# Embed
query_embed_response = portrai_agent.client.models.embed_content(
    model='text-embedding-004',
    contents=query,
)
query_embedding = query_embed_response.embeddings[0].values

from apps.backend.src.agent.portrai_cms_agent import cosine_similarity
import numpy as np

similarities = [cosine_similarity(query_embedding, doc_emb) for doc_emb in portrai_agent.chunk_embeddings]
top_k = 5
top_indices = np.argsort(similarities)[-top_k:][::-1]

for i in top_indices:
    print(f"Chunk {i} similarity: {similarities[i]}")
    print(f"Content: {portrai_agent.chunks[i][:100]}...\n")
