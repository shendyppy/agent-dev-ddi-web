"""Tests for the relevance judgement in agent.relevance.

The decision under test is silent when wrong: which retrieved passages the
agent treats as evidence. Get it wrong in one direction and the answer quotes
a table of contents; wrong in the other and a question the index can answer
comes back as "nothing found".

Most of these encode a specific measurement against the real index rather than
a preference — the docstrings say which. Changing a threshold in
``relevance.py`` should make one of them fail loudly, not pass quietly.
"""

from __future__ import annotations

from .relevance import RankedChunk, _select_best_chunks, confidence, rank


def _chunk(
    score: float | None,
    source: str = "a.md",
    text: str = "isi dokumen",
    heading: str = "",
) -> dict[str, object]:
    chunk: dict[str, object] = {
        "text": text,
        "source": source,
        "metadata": {"heading_path": heading} if heading else {},
    }
    if score is not None:
        chunk["score"] = score
    return chunk


class TestSelectBestChunks:
    """`search_documentation` returns a fixed top_k regardless of quality, so
    the tail of its list is usually a chunk that merely shares a word with the
    question. Printing it all buries the passage that actually answers."""

    def test_keeps_the_best_match_and_its_near_ties(self) -> None:
        selected = _select_best_chunks([_chunk(0.82, "a.md"), _chunk(0.78, "b.md")])
        assert [c["source"] for c in selected] == ["a.md", "b.md"]

    def test_drops_matches_clearly_worse_than_the_best(self) -> None:
        selected = _select_best_chunks(
            [_chunk(0.82, "a.md"), _chunk(0.45, "b.md"), _chunk(0.31, "c.md")]
        )
        assert [c["source"] for c in selected] == ["a.md"]

    def test_orders_by_score_regardless_of_input_order(self) -> None:
        selected = _select_best_chunks([_chunk(0.75, "b.md"), _chunk(0.80, "a.md")])
        assert [c["source"] for c in selected] == ["a.md", "b.md"]

    def test_caps_the_number_of_passages(self) -> None:
        selected = _select_best_chunks([_chunk(0.80, f"{i}.md") for i in range(6)])
        assert len(selected) == 3

    def test_nothing_relevant_when_even_the_best_is_weak(self) -> None:
        """A wall of near-misses is worse than admitting the index has nothing:
        it looks authoritative and answers a different question."""
        assert _select_best_chunks([_chunk(0.12), _chunk(0.05), _chunk(-0.3)]) == []

    def test_unscored_chunks_fall_back_to_retriever_order(self) -> None:
        """A retriever that does not score at all must not be read as empty."""
        chunks = [_chunk(None, f"{i}.md") for i in range(5)]
        selected = _select_best_chunks(chunks)
        assert [c["source"] for c in selected] == ["0.md", "1.md", "2.md"]

    def test_empty_input_stays_empty(self) -> None:
        assert _select_best_chunks([]) == []


class TestKeywordGate:
    """Measured against the real index, the similarity score cannot tell an
    off-topic Indonesian question ("resep rendang padang", top score 0.514) from
    an on-topic one ("gimana cara menjalankan proyek ini di lokal?", 0.501) —
    bge-small-en reads all Indonesian text as roughly equidistant. Keyword
    overlap separated the same queries cleanly (on topic 3-10, off topic 0-1),
    so overlap gates and the score only breaks ties."""

    QUESTION = "gimana cara menjalankan proyek ini di lokal?"

    def test_how_to_framing_does_not_make_a_passage_relevant(self) -> None:
        """`cara` is in most headings of this corpus ("Cara Menjalankan", "Cara
        Membaca", "Cara Kerja"), so it cannot be allowed to count: a contents
        page whose only tie to the question is the word "cara" is eliminated
        outright, not merely ranked second."""
        toc = _chunk(0.50, "toc.md", heading="Cara Membaca Dokumen Ini", text="daftar isi")
        answer = _chunk(
            0.49,
            "run.md",
            heading="Tech Stack > Menjalankan di lokal",
            text="npm i lalu npm run dev untuk proyek ini",
        )
        selected = _select_best_chunks([toc, answer], self.QUESTION)
        assert [c["source"] for c in selected] == ["run.md"]

    def test_off_topic_how_to_questions_are_rejected(self) -> None:
        """The regression this stopword group exists for: "gimana cara bikin kopi
        susu" used to come back with a documentation contents page."""
        toc = _chunk(
            0.49, "toc.md", heading="TEP CMS > Cara Membaca Dokumen Ini", text="cara bikin"
        )
        assert _select_best_chunks([toc], "gimana cara bikin kopi susu yang enak") == []

    def test_short_product_acronyms_still_count(self) -> None:
        """A four-character floor threw away `tep` and `cms` — the two words that
        identify the product — and answered "nothing found" to a question the
        index had a 0.662 match for."""
        chunk = _chunk(
            0.66,
            "tep.md",
            heading="TEP CMS — Feature Context > Tech Stack",
            text="React, Vite, Tailwind",
        )
        selected = _select_best_chunks([chunk], "teknologi apa yang dipakai di TEP CMS?")
        assert [c["source"] for c in selected] == ["tep.md"]

    def test_a_short_word_does_not_match_mid_token(self) -> None:
        """Prefix-of-token, not substring-of-text: as a bare substring `tep`
        would hit "step" and `api` would hit "aplikasi"."""
        decoy = _chunk(0.60, "decoy.md", heading="Langkah Setup", text="step by step aplikasi ini")
        assert _select_best_chunks([decoy], "TEP API") == []

    def test_a_titled_section_beats_a_table_of_contents(self) -> None:
        """The exact shape observed against the real index: a contents table
        mentions every topic in its cells, so on body text alone it ties with
        the section that answers. The heading is what breaks it."""
        toc = _chunk(
            0.50,
            "toc.md",
            heading="TEP CMS > Cara Membaca Dokumen Ini",
            text="| Cara jalanin di lokal | Tech Stack & Cara Menjalankan |",
        )
        answer = _chunk(
            0.49,
            "run.md",
            heading="TEP CMS > Cara Menjalankan > Menjalankan di lokal",
            text="npm i lalu npm run dev",
        )
        selected = _select_best_chunks([toc, answer], self.QUESTION)
        assert [c["source"] for c in selected] == ["run.md", "toc.md"]

    def test_a_high_score_does_not_survive_zero_overlap(self) -> None:
        """The consequence of trusting overlap over the score: a chunk that
        mentions nothing the user asked about is dropped even at 0.82, because on
        this corpus a high score is not evidence of being on topic."""
        mute = _chunk(0.82, "mute.md", text="tidak menyebut kata apa pun")
        on_topic = _chunk(0.40, "on-topic.md", heading="Menjalankan di lokal", text="npm run dev")
        selected = _select_best_chunks([mute, on_topic], self.QUESTION)
        assert [c["source"] for c in selected] == ["on-topic.md"]

    def test_score_breaks_ties_between_equally_on_topic_passages(self) -> None:
        weaker = _chunk(0.45, "weaker.md", heading="Menjalankan di lokal", text="npm run dev")
        stronger = _chunk(0.61, "stronger.md", heading="Menjalankan di lokal", text="npm run dev")
        selected = _select_best_chunks([weaker, stronger], self.QUESTION)
        assert [c["source"] for c in selected] == ["stronger.md", "weaker.md"]

    def test_nothing_on_topic_returns_nothing(self) -> None:
        """The off-topic case that a score floor could not catch: decent scores,
        no shared vocabulary at all."""
        chunks = [
            _chunk(0.52, "a.md", heading="Manajemen Assessment", text="modul penilaian peserta"),
            _chunk(0.51, "b.md", heading="Peta Route", text="daftar halaman aplikasi"),
        ]
        assert _select_best_chunks(chunks, "resep rendang padang untuk lebaran") == []

    def test_a_question_with_no_content_words_falls_back_to_score(self) -> None:
        """Nothing to overlap against, so refusing to answer would be worse than
        a weak guess ranked by score."""
        selected = _select_best_chunks([_chunk(0.75, "b.md"), _chunk(0.80, "a.md")], "apa itu ini?")
        assert [c["source"] for c in selected] == ["a.md", "b.md"]

    def test_a_single_word_question_cannot_be_held_to_the_two_point_bar(self) -> None:
        """One content word found in the body scores 1, so a bar of 2 would
        reject every passage for a one-word question."""
        selected = _select_best_chunks(
            [_chunk(0.55, "a.md", text="modul assessment untuk peserta")], "assessment"
        )
        assert [c["source"] for c in selected] == ["a.md"]

    def test_grammar_words_do_not_count_as_topic(self) -> None:
        """Without a stopword guard, "ini"/"yang" would hand the tie to whichever
        chunk happens to be the most verbose."""
        chatty = _chunk(0.50, "chatty.md", text="ini yang itu dengan untuk dari pada proyek ini")
        precise = _chunk(0.50, "precise.md", heading="Menjalankan di lokal", text="npm run dev")
        selected = _select_best_chunks([chatty, precise], self.QUESTION)
        assert selected[0]["source"] == "precise.md"


# ─── The display projection ──────────────────────────────────────────
# `rank` and `confidence` feed the `retrieval` SSE event and the frontend's
# EvidencePanel. They must agree with `_select_best_chunks` about what counts —
# a panel that says "3 passages used" while the answer quotes different ones is
# worse than no panel at all.


class TestRank:
    QUESTION = "gimana cara menjalankan proyek ini di lokal?"

    def test_strong_verdicts_match_what_the_answer_uses(self) -> None:
        """The invariant that keeps the panel honest."""
        chunks = [
            _chunk(0.50, "toc.md", heading="Cara Membaca Dokumen Ini", text="daftar isi"),
            _chunk(0.49, "run.md", heading="Menjalankan di lokal", text="npm run dev proyek"),
        ]
        strong = [r.source for r in rank(chunks, self.QUESTION) if r.verdict == "strong"]
        assert strong == [c["source"] for c in _select_best_chunks(chunks, self.QUESTION)]

    def test_rejected_passages_are_reported_not_dropped(self) -> None:
        """The whole point of the panel: a reader has to SEE that the 0.52
        passage scored higher than the one that answered and was still thrown
        out, or the score-is-misleading lesson never lands."""
        chunks = [
            _chunk(0.52, "rendang.md", heading="Manajemen Assessment", text="penilaian peserta"),
            _chunk(0.49, "run.md", heading="Menjalankan di lokal", text="npm run dev proyek"),
        ]
        ranked = rank(chunks, self.QUESTION)
        assert len(ranked) == 2
        by_source = {r.source: r for r in ranked}
        assert by_source["run.md"].verdict == "strong"
        assert by_source["rendang.md"].verdict == "rejected"
        # The uncomfortable part, stated as an assertion so it cannot rot.
        assert by_source["rendang.md"].score > by_source["run.md"].score

    def test_accepted_passages_come_before_rejected_ones(self) -> None:
        chunks = [
            _chunk(0.80, "mute.md", text="tidak menyebut apa pun"),
            _chunk(0.30, "run.md", heading="Menjalankan di lokal", text="npm run dev proyek"),
        ]
        assert [r.verdict for r in rank(chunks, self.QUESTION)] == ["strong", "rejected"]

    def test_passages_past_the_cap_are_weak_not_rejected(self) -> None:
        """They cleared every gate and only lost the cap. Calling that
        "rejected" would misreport why they are not in the answer."""
        chunks = [
            _chunk(0.50 + i / 100, f"{i}.md", heading="Menjalankan di lokal", text="proyek lokal")
            for i in range(5)
        ]
        verdicts = [r.verdict for r in rank(chunks, self.QUESTION)]
        assert verdicts == ["strong", "strong", "strong", "weak", "weak"]

    def test_overlap_is_exposed_for_every_passage(self) -> None:
        """Including the rejected ones — a zero is the most informative value
        the panel can show."""
        chunks = [_chunk(0.52, "off.md", heading="Peta Route", text="daftar halaman")]
        assert rank(chunks, self.QUESTION)[0].overlap == 0

    def test_heading_falls_back_to_the_source_path(self) -> None:
        ranked = rank([_chunk(0.60, "docs/run.md", text="npm run dev proyek lokal")], self.QUESTION)
        assert ranked[0].heading == "docs/run.md"

    def test_excerpt_is_trimmed_and_whitespace_collapsed(self) -> None:
        long_text = "proyek lokal " + ("x" * 500)
        ranked = rank([_chunk(0.60, "a.md", text=long_text)], self.QUESTION)
        assert len(ranked[0].excerpt) <= 241
        assert ranked[0].excerpt.endswith("…")

    def test_empty_retrieval_ranks_to_nothing(self) -> None:
        assert rank([], self.QUESTION) == []


class TestConfidence:
    QUESTION = "gimana cara menjalankan proyek ini di lokal?"

    def _c(self, *ranked: RankedChunk) -> str:
        return confidence(list(ranked))

    def test_nothing_accepted_is_none(self) -> None:
        """The honest dead end — this is what makes the agent say "I did not
        find anything close enough" instead of quoting something else."""
        chunks = [
            _chunk(0.52, "a.md", heading="Manajemen Assessment", text="penilaian peserta"),
            _chunk(0.51, "b.md", heading="Peta Route", text="daftar halaman"),
        ]
        assert confidence(rank(chunks, "resep rendang padang untuk lebaran")) == "none"

    def test_a_heading_match_plus_body_words_is_high(self) -> None:
        chunks = [
            _chunk(
                0.49,
                "run.md",
                heading="Cara Menjalankan > Menjalankan di lokal",
                text="jalankan proyek ini di lokal dengan npm run dev",
            )
        ]
        assert confidence(rank(chunks, self.QUESTION)) == "high"

    def test_a_bare_two_word_body_match_is_medium(self) -> None:
        chunks = [_chunk(0.49, "run.md", text="proyek lokal")]
        assert confidence(rank(chunks, self.QUESTION)) == "medium"

    def test_a_single_word_match_is_low(self) -> None:
        """Only reachable through the one-word-question relaxation, which is
        exactly the case where the agent should hedge."""
        chunks = [_chunk(0.55, "a.md", text="modul assessment untuk peserta")]
        assert confidence(rank(chunks, "assessment")) == "low"

    def test_a_scored_question_with_no_content_words_is_low(self) -> None:
        """Ranked by score alone, so there is no overlap evidence to be
        confident about."""
        assert confidence(rank([_chunk(0.80, "a.md")], "apa itu ini?")) == "low"

    def test_empty_ranking_is_none(self) -> None:
        assert self._c() == "none"
