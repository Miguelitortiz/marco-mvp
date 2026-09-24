"""Word/page budget enforcement, independent from any LLM provider."""
from dataclasses import dataclass
import re


@dataclass(frozen=True)
class BudgetResult:
    words: int
    pages: float
    minimum_words: int
    maximum_words: int
    within_budget: bool


class BudgetEnforcer:
    def __init__(self, target_words: int = 500, *, target_pages: float | None = None,
                 tolerance: float = 0.10, words_per_page: int = 500) -> None:
        if target_words < 1 or tolerance < 0 or tolerance >= 1:
            raise ValueError("target_words must be positive and tolerance in [0, 1)")
        self.target_words, self.target_pages = target_words, target_pages
        self.tolerance, self.words_per_page = tolerance, words_per_page

    def check(self, text: str, pages: float | None = None) -> BudgetResult:
        words = len(re.findall(r"\w+", text, flags=re.UNICODE))
        actual_pages = pages if pages is not None else words / self.words_per_page
        minimum = int(self.target_words * (1 - self.tolerance))
        maximum = int(self.target_words * (1 + self.tolerance))
        page_ok = (self.target_pages is None or
                    self.target_pages * (1 - self.tolerance) <= actual_pages <=
                    self.target_pages * (1 + self.tolerance))
        return BudgetResult(words, actual_pages, minimum, maximum,
                            minimum <= words <= maximum and page_ok)

    enforce = check
