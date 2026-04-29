from typing import List, Callable, Any

class ReasoningLoops:
    """Provide helpers for Chain-of-Thought and a simple Tree-of-Thoughts stub.

    This is a lightweight implementation: ToT is implemented as best-first expansion
    using a user-provided evaluator function that scores partial thoughts.
    """

    @staticmethod
    def chain_of_thought_prompt(task: str, steps_hint: int = 5) -> str:
        return f"Please think step-by-step and show your chain-of-thought in {steps_hint} steps before the final answer.\n\nTask: {task}"

    @staticmethod
    def tree_of_thoughts(seed: str, generator: Callable[[str], List[str]], evaluator: Callable[[str], float], depth: int = 2, width: int = 3) -> str:
        # Simple breadth expansion with scoring
        frontier = [seed]
        best = seed
        best_score = evaluator(seed)
        for d in range(depth):
            candidates = []
            for node in frontier:
                expansions = generator(node)[:width]
                for e in expansions:
                    score = evaluator(e)
                    candidates.append((score, e))
                    if score > best_score:
                        best_score = score
                        best = e
            # Keep top-k as new frontier
            candidates.sort(key=lambda t: t[0], reverse=True)
            frontier = [c[1] for c in candidates[:width]]
        return best
