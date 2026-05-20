from duckduckgo_search import DDGS

company = "Nicobar Design Pvt Ltd"
query = f'"{company}" funding OR valuation OR growth OR raised 2024 OR 2025'
with DDGS() as ddgs:
    results = list(ddgs.text(query, max_results=3))
    print(f"Results for [{query}]: {results}")
