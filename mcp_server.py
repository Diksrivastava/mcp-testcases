import os
import csv
import json
from typing import List, Dict, Any, Optional
from mcp.server.fastmcp import FastMCP

# Create the MCP server
mcp = FastMCP("Test Cases MCP")

CSV_PATH = os.path.join(os.path.dirname(__file__), "testcases_vwo_5000.csv")

# Load data into memory on start for ultra-fast queries
test_cases: List[Dict[str, str]] = []
test_cases_by_id: Dict[str, Dict[str, str]] = {}

def load_data():
    global test_cases, test_cases_by_id
    if not os.path.exists(CSV_PATH):
        raise FileNotFoundError(f"CSV file not found at {CSV_PATH}")
    
    with open(CSV_PATH, mode="r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            # clean fields
            row_dict = {k.strip(): v.strip() if v else "" for k, v in row.items()}
            # Add to list and map
            tc_id = row_dict.get("id")
            if tc_id:
                test_cases.append(row_dict)
                test_cases_by_id[tc_id.upper()] = row_dict

# Load CSV data
load_data()

@mcp.tool()
def list_test_cases(limit: int = 50, offset: int = 0) -> str:
    """
    List test cases with pagination.
    
    Args:
        limit (int): Maximum number of test cases to return (default 50, max 200).
        offset (int): Number of test cases to skip.
    """
    limit = min(limit, 200)
    selected = test_cases[offset : offset + limit]
    
    response = {
        "total_test_cases": len(test_cases),
        "limit": limit,
        "offset": offset,
        "count": len(selected),
        "test_cases": [
            {
                "id": tc.get("id", ""),
                "jira_id": tc.get("jira_id", ""),
                "summary": tc.get("summary", ""),
                "priority": tc.get("priority", ""),
                "module": tc.get("module", ""),
                "status": tc.get("status", ""),
            }
            for tc in selected
        ]
    }
    return json.dumps(response, indent=2)

@mcp.tool()
def get_test_case(id: str) -> str:
    """
    Get detailed information about a single test case by its unique ID (e.g. 'TC-00001').
    
    Args:
        id (str): Unique test case identifier (e.g. 'TC-00001').
    """
    tc_id = id.strip().upper()
    tc = test_cases_by_id.get(tc_id)
    if not tc:
        return json.dumps({"error": f"Test case with ID {id} not found."}, indent=2)
    return json.dumps(tc, indent=2)

@mcp.tool()
def search_test_cases(
    query: Optional[str] = None,
    priority: Optional[str] = None,
    module: Optional[str] = None,
    severity: Optional[str] = None,
    status: Optional[str] = None,
    test_type: Optional[str] = None,
    owner: Optional[str] = None,
    label: Optional[str] = None,
    limit: int = 50
) -> str:
    """
    Search and filter VWO test cases. Supports full-text search across summary, preconditions, 
    steps, and expected result, along with targeted metadata filtering.
    
    Args:
        query (str): Optional search text to match in summary, steps, preconditions, expected result, or jira_id.
        priority (str): Filter by priority (e.g., 'P0', 'P1', 'P2', 'P3').
        module (str): Filter by module name (e.g., 'Reports', 'Editor', 'Goals', 'AB Testing').
        severity (str): Filter by severity (e.g., 'Major', 'Minor', 'Blocker', 'Critical', 'Trivial').
        status (str): Filter by status (e.g., 'Active', 'Archived', 'Draft').
        test_type (str): Filter by test type (e.g., 'Functional', 'Performance', 'Security', 'Negative', 'Boundary', 'UI').
        owner (str): Filter by owner email or name (e.g., 'aditya.rao').
        label (str): Filter by label/tag (e.g., 'regression', 'sanity', 'smoke', 'firefox').
        limit (int): Maximum number of search results to return (default 50, max 200).
    """
    limit = min(limit, 200)
    results = []
    
    query_lower = query.lower().strip() if query else None
    priority_upper = priority.upper().strip() if priority else None
    module_lower = module.lower().strip() if module else None
    severity_lower = severity.lower().strip() if severity else None
    status_lower = status.lower().strip() if status else None
    type_lower = test_type.lower().strip() if test_type else None
    owner_lower = owner.lower().strip() if owner else None
    label_lower = label.lower().strip() if label else None
    
    for tc in test_cases:
        # 1. Query search
        if query_lower:
            text_to_search = " ".join([
                tc.get("summary", ""),
                tc.get("preconditions", ""),
                tc.get("steps", ""),
                tc.get("expected_result", ""),
                tc.get("jira_id", ""),
                tc.get("id", "")
            ]).lower()
            if query_lower not in text_to_search:
                continue
        
        # 2. Priority filter
        if priority_upper and tc.get("priority", "").upper().strip() != priority_upper:
            continue
            
        # 3. Module filter
        if module_lower and tc.get("module", "").lower().strip() != module_lower:
            continue
            
        # 4. Severity filter
        if severity_lower and tc.get("severity", "").lower().strip() != severity_lower:
            continue
            
        # 5. Status filter
        if status_lower and tc.get("status", "").lower().strip() != status_lower:
            continue
            
        # 6. Test Type filter
        if type_lower and tc.get("test_type", "").lower().strip() != type_lower:
            continue
            
        # 7. Owner filter
        if owner_lower and owner_lower not in tc.get("owner", "").lower():
            continue
            
        # 8. Label filter
        if label_lower:
            labels_list = [l.strip().lower() for l in tc.get("labels", "").split("|")]
            if label_lower not in labels_list:
                continue
                
        results.append(tc)
        if len(results) >= limit:
            break
            
    response = {
        "count": len(results),
        "limit": limit,
        "test_cases": results
    }
    return json.dumps(response, indent=2)

@mcp.resource("testcases://stats")
def get_stats() -> str:
    """
    Get high-level statistics of the test case repository (e.g. count by priority, module, status).
    """
    total = len(test_cases)
    priorities = {}
    severities = {}
    modules = {}
    statuses = {}
    test_types = {}
    
    for tc in test_cases:
        p = tc.get("priority", "Unknown")
        priorities[p] = priorities.get(p, 0) + 1
        
        s = tc.get("severity", "Unknown")
        severities[s] = severities.get(s, 0) + 1
        
        m = tc.get("module", "Unknown")
        modules[m] = modules.get(m, 0) + 1
        
        st = tc.get("status", "Unknown")
        statuses[st] = statuses.get(st, 0) + 1
        
        tt = tc.get("test_type", "Unknown")
        test_types[tt] = test_types.get(tt, 0) + 1
        
    stats = {
        "total_test_cases": total,
        "priority_breakdown": priorities,
        "severity_breakdown": severities,
        "module_breakdown": modules,
        "status_breakdown": statuses,
        "test_type_breakdown": test_types
    }
    return json.dumps(stats, indent=2)

@mcp.resource("testcases://all")
def get_all_test_cases() -> str:
    """
    Get all 5,000 VWO test cases in the repository.
    """
    return json.dumps(test_cases, indent=2)

@mcp.resource("testcases://{tc_id}")
def get_test_case_resource(tc_id: str) -> str:
    """
    Get detailed information about a single VWO test case by its ID.
    """
    tc = test_cases_by_id.get(tc_id.upper().strip())
    if not tc:
        return json.dumps({"error": f"Test case with ID {tc_id} not found."}, indent=2)
    return json.dumps(tc, indent=2)


@mcp.prompt()
def search_by_query_and_priority(query: str = "", priority: str = "P0") -> str:
    """
    Prompt template to search and analyze VWO test cases by query text and priority.
    """
    return f"Search for VWO test cases matching the query '{query}' and priority '{priority}'. Present them in a neat table and summarize the execution steps."

@mcp.prompt()
def explain_module_scenarios(module: str = "AB Testing") -> str:
    """
    Prompt template to list and analyze test cases for a specific product module.
    """
    return f"Look up all test cases under the module '{module}'. List the main verification objectives and summarize the key preconditions."

if __name__ == "__main__":
    mcp.run()

