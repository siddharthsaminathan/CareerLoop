from duckduckgo_search import DDGS

with DDGS() as ddgs:
    results = list(ddgs.text("Nicobar lifestyle company about", max_results=3))
    print(f"Results: {results}")
