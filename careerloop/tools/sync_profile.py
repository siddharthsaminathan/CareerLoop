import os
import yaml

def sync_profile_data(temp_profile_data: dict) -> str:
    """
    Syncs the user's temp_profile_data (roles, cities, salary) from the database
    into portals.yml so that the Node.js scanner knows what to search for.
    """
    if not temp_profile_data:
        return "No profile data provided to sync."
        
    target_roles = temp_profile_data.get("target_roles", "")
    
    portals_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "portals.yml"))
    templates_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "templates", "portals.example.yml"))
    
    source_path = portals_path if os.path.exists(portals_path) else templates_path
    if not os.path.exists(source_path):
        return "Could not find portals.yml or templates/portals.example.yml"
        
    try:
        with open(source_path, 'r') as f:
            config = yaml.safe_load(f)
            
        # Extract target roles correctly handling newlines or commas
        if target_roles:
            roles = []
            for line in target_roles.replace(',', '\n').split('\n'):
                clean_role = line.replace('-', '').strip()
                if clean_role:
                    roles.append(clean_role)
                    
            if roles and 'title_filter' in config:
                existing = set(config['title_filter'].get('positive', []))
                for r in roles:
                    existing.add(r)
                config['title_filter']['positive'] = list(existing)
                
        with open(portals_path, 'w') as f:
            yaml.dump(config, f, sort_keys=False)
            
        return f"Successfully synced portals.yml with target roles: {roles}"
    except Exception as e:
        return f"Error syncing portals.yml: {e}"
