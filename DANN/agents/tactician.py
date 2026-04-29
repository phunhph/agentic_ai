import datetime

class TacticianAgent:
	"""Suggest tactical next actions for a given opportunity or account.

	This is a simple rule-based starter. It can be extended to call an LLM.
	"""
	def __init__(self, model=None, llm_url=None):
		self.model = model
		self.llm_url = llm_url

	def suggest_actions(self, extracted_data: dict):
		suggestions = []
		name = extracted_data.get('name') or 'this opportunity'
		budget = extracted_data.get('budget')

		if budget and budget >= 100000:
			suggestions.append(f"High-value: Propose scheduling executive briefing for {name} within 3 business days.")
		else:
			suggestions.append(f"Send pricing summary email for {name} and ask for decision timeline.")

		suggestions.append("Check technical fit and attach standard SLA; if custom, escalate to SE.")
		suggestions.append(f"Suggested follow-up date: {(datetime.date.today() + datetime.timedelta(days=7)).isoformat()}")

		return suggestions
