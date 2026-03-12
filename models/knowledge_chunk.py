from odoo import api, fields, models


class KnowledgeChunk(models.Model):
    _name = "dc.knowledge.chunk"
    _description = "Dragon Coders Knowledge Chunk"
    _order = "document_id, sequence"

    document_id = fields.Many2one(
        "dc.knowledge.document",
        string="Document",
        required=True,
        ondelete="cascade",
    )
    content = fields.Text(string="Chunk Content", required=True)
    category = fields.Char(string="Category")
    sequence = fields.Integer(string="Order", default=0)

    @api.model
    def get_relevant_chunks(self, query, limit=5):
        """
        Keyword-based retrieval.
        Finds the most relevant chunks for a given query
        from all ready documents in the knowledge base.
        """
        from odoo import api

        query_words = set(query.lower().split())

        # Remove common stop words
        stop_words = {
            "a",
            "an",
            "the",
            "is",
            "it",
            "in",
            "on",
            "at",
            "to",
            "for",
            "of",
            "and",
            "or",
            "are",
            "was",
            "be",
            "do",
            "does",
            "have",
            "has",
            "what",
            "how",
            "when",
            "where",
            "who",
            "which",
            "can",
            "you",
            "we",
            "i",
            "me",
            "my",
            "your",
            "our",
            "this",
            "that",
            "with",
            "from",
            "by",
            "about",
            "will",
            "would",
            "could",
            "should",
        }
        keywords = query_words - stop_words

        if not keywords:
            return self.search([], limit=limit)

        # Only search chunks from ready documents
        all_chunks = self.search(
            [
                ("document_id.state", "=", "ready"),
                ("document_id.active", "=", True),
            ]
        )

        # Score each chunk by keyword overlap
        scored = []
        for chunk in all_chunks:
            content_lower = chunk.content.lower()
            score = sum(1 for kw in keywords if kw in content_lower)
            # Bonus for exact phrase match
            if query.lower() in content_lower:
                score += 5
            if score > 0:
                scored.append((score, chunk))

        # Sort by score descending, return top N
        scored.sort(key=lambda x: x[0], reverse=True)
        return [c for _, c in scored[:limit]]
