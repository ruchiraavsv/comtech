"""Fixed query-embedding port, owned by trusted API code, never generated Python."""

import math

from comtech.research.accounting import embed


class QueryEmbedding:
    def __init__(self, client, counter, *, model, dimensions):
        self.client, self.counter = client, counter
        self.model, self.dimensions = model, dimensions

    async def __call__(self, query):
        if not isinstance(query, str) or not query.strip() or len(query) > 1000:
            raise ValueError("Invalid query embedding input")
        response = await embed(
            lambda: self.client.embeddings.create(
                model=self.model, dimensions=self.dimensions, input=[query]
            ),
            self.counter.count(query) + 32,
        )
        vector = response.data[0].embedding
        if len(vector) != self.dimensions or not all(math.isfinite(v) for v in vector):
            raise ValueError("Invalid query embedding response")
        return vector
