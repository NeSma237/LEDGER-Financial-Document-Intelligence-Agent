import httpx, ast, operator, os

RETRIEVAL_URL = os.getenv("RETRIEVAL_URL", "http://localhost:8001")

def search_documents(query: str, top_k: int = 10) -> list:
    try:
        r = httpx.post(f"{RETRIEVAL_URL}/search_documents",
                       json={"query": query, "top_k": top_k}, timeout=10)
        return r.json()["results"]
    except:
        return []

def search_tables(query: str, top_k: int = 10) -> list:
    try:
        r = httpx.post(f"{RETRIEVAL_URL}/search_tables",
                       json={"query": query, "top_k": top_k}, timeout=10)
        return r.json()["results"]
    except:
        return []

def filter_documents(metadata: dict) -> list:
    try:
        r = httpx.post(f"{RETRIEVAL_URL}/filter_documents",
                       json=metadata, timeout=10)
        return r.json()["results"]
    except:
        return []

def calculate(expression: str) -> dict:
    try:
        result = _safe_eval(expression)
        return {"result": round(result, 4), "formula": expression, "error": None}
    except Exception as e:
        return {"result": None, "formula": expression, "error": str(e)}

def _safe_eval(expr: str) -> float:
    tree = ast.parse(expr, mode='eval')
    return _eval_node(tree.body)

def _eval_node(node):
    import ast as a
    if isinstance(node, a.Constant):
        return float(node.value)
    elif isinstance(node, a.BinOp):
        ops = {
            a.Add: operator.add, a.Sub: operator.sub,
            a.Mult: operator.mul, a.Div: operator.truediv,
            a.Pow: operator.pow
        }
        return ops[type(node.op)](_eval_node(node.left), _eval_node(node.right))
    elif isinstance(node, a.Call):
        if isinstance(node.func, a.Name) and node.func.id == 'abs':
            return abs(_eval_node(node.args[0]))
    elif isinstance(node, a.UnaryOp) and isinstance(node.op, a.USub):
        return -_eval_node(node.operand)
    raise ValueError(f"Unsupported expression: {node}")