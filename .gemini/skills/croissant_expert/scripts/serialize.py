import json
import sys
import os

# Import NLP Expert logic if available
try:
    sys.path.append(os.path.join(os.path.dirname(__file__), '../../nlp_expert/scripts'))
    from extract_entities import extract_entities
except ImportError:
    extract_entities = None

def create_croissant_jsonld(metadata):
    """
    Creates a valid Croissant JSON-LD structure based on provided metadata.
    """
    context = {
        "@language": "en",
        "@vocab": "https://schema.org/",
        "cr": "http://mlcommons.org/croissant/",
        "sc": "https://schema.org/",
        "dct": "http://purl.org/dc/terms/",
        "conformsTo": "dct:conformsTo",
        "recordSet": "cr:recordSet",
        "field": "cr:field",
        "source": "cr:source",
        "fileObject": "cr:fileObject",
        "fileSet": "cr:fileSet",
        "dataType": { "@id": "cr:dataType", "@type": "@id" }
    }

    distribution_list = []
    record_set_list = []

    creator_list = metadata.get("creator", [])
    if not isinstance(creator_list, list):
        creator_list = [creator_list]
        
    publisher_list = metadata.get("publisher", [])
    if not isinstance(publisher_list, list):
        publisher_list = [publisher_list]
        
    spatial_list = metadata.get("spatialCoverage", [])
    if not isinstance(spatial_list, list):
        spatial_list = [spatial_list]
        
    temporal_list = metadata.get("temporalCoverage", [])
    if not isinstance(temporal_list, list):
        temporal_list = [temporal_list]

    keywords_list = metadata.get("keywords", [])
    if not isinstance(keywords_list, list):
        keywords_list = [keywords_list]

    # Multi-lingual support helper
    def format_multilingual(value, default_lang="en"):
        if value is None:
            return None
        if isinstance(value, dict) and "@value" in value:
            return value
        if isinstance(value, str):
            # If it's empty, return None
            if not value.strip():
                return None
            return { "@language": default_lang, "@value": value }
        return value

    def is_duplicate(item_val, collection):
        """Robust check for duplicates in a list of multilingual dicts, complex objects, or strings."""
        def get_val(item):
            if isinstance(item, dict):
                if "@value" in item: return str(item["@value"])
                if "name" in item:
                    n = item["name"]
                    if isinstance(n, dict) and "@value" in n: return str(n["@value"])
                    if isinstance(n, list) and len(n) > 0:
                        # Handle list of multilingual names
                        first = n[0]
                        if isinstance(first, dict) and "@value" in first: return str(first["@value"])
                        return str(first)
                    return str(n)
            return str(item)

        val_to_check = get_val(item_val)
        for c in collection:
            c_val = get_val(c)
            if c_val.lower() == val_to_check.lower():
                return True
        return False

    dataset = {
        "@context": context,
        "@type": "sc:Dataset",
        "name": format_multilingual(metadata.get("name", "Untitled Dataset")),
        "description": format_multilingual(metadata.get("description", "No description provided.")),
        "url": metadata.get("url", "https://example.com/dataset"),
        "license": metadata.get("license", "CC-BY-4.0"),
        "dct:conformsTo": "http://mlcommons.org/croissant/1.0",
        "datePublished": metadata.get("datePublished") or metadata.get("uploadDate"),
        "version": metadata.get("version", "1.0"),
        "distribution": distribution_list,
        "recordSet": record_set_list,
        "creator": creator_list,
        "publisher": publisher_list,
        "author": metadata.get("author"),
        "spatialCoverage": spatial_list,
        "temporalCoverage": temporal_list,
        "keywords": keywords_list
    }

    # Enrich with NLP if requested
    if metadata.get("apply_nlp") and extract_entities:
        print(f"> Applying NLP analysis for: {metadata.get('name', 'Dataset')}")
        text_to_analyze = metadata.get("nlp_text") or f"{dataset['name']} {dataset['description']}"
        entities = extract_entities(text_to_analyze)
        if entities:
            elements = entities.get("itemListElement", [])
            for el in elements:
                item = el.get("item") if isinstance(el.get("item"), dict) else el
                etype = item.get("@type", "")
                ename = item.get("name", "")
                ename_orig = item.get("name_original")
                elang = item.get("language")
                
                if not ename: continue

                m_name = format_multilingual(ename, "en")
                m_list = [m_name]
                if ename_orig and elang:
                    m_list.append(format_multilingual(ename_orig, elang))

                # Normalize type
                etype = etype.replace("sc:", "")

                if etype in ["Person", "Organization", "CollegeOrUniversity", "EducationalOrganization"]:
                    role_type = "sc:Person" if etype == "Person" else "sc:Organization"
                    if not is_duplicate(ename, creator_list):
                        creator_list.append({"@type": role_type, "name": m_list[0] if len(m_list) == 1 else m_list})
                elif etype in ["Place", "City", "Country", "Landmark", "AdministrativeArea"]:
                    for mn in m_list:
                        if not is_duplicate(mn, spatial_list):
                            spatial_list.append(mn)
                elif etype in ["Event", "Date", "Duration", "TemporalEntity"]:
                    date_val = item.get("startDate") or ename
                    m_date = format_multilingual(date_val, "en")
                    d_list = [m_date]
                    if ename_orig and elang:
                        d_list.append(format_multilingual(ename_orig, elang))
                    
                    for md in d_list:
                        if not is_duplicate(md, temporal_list):
                            temporal_list.append(md)
                
                # Always add to keywords
                for mn in m_list:
                    if not is_duplicate(mn, keywords_list):
                        keywords_list.append(mn)

    # Clean up empty optional fields
    if not creator_list: dataset.pop("creator", None)
    if not publisher_list: dataset.pop("publisher", None)
    if not spatial_list: dataset.pop("spatialCoverage", None)
    if not temporal_list: dataset.pop("temporalCoverage", None)
    if not keywords_list: dataset.pop("keywords", None)

    # Handle distribution
    for dist in metadata.get("distribution", []):
        dist_type = dist.get("type", "FileObject")
        obj = {}
        if dist_type == "FileObject":
            obj = {
                "@type": "cr:FileObject",
                "name": dist.get("name"),
                "contentUrl": dist.get("contentUrl"),
                "encodingFormat": dist.get("encodingFormat"),
                "sha256": dist.get("sha256"),
                "unf": dist.get("unf")
            }
        elif dist_type == "FileSet":
            obj = {
                "@type": "cr:FileSet",
                "name": dist.get("name"),
                "containedIn": dist.get("containedIn"),
                "encodingFormat": dist.get("encodingFormat"),
                "includes": dist.get("includes"),
                "unf": dist.get("unf")
            }
        
        # Clean up null values
        clean_obj = {k: v for k, v in obj.items() if v is not None}
        if clean_obj:
            distribution_list.append(clean_obj)

    # Handle recordSets
    for rs in metadata.get("recordSet", []):
        fields_list = []
        record_set = {
            "@type": "cr:RecordSet",
            "name": rs.get("name"),
            "field": fields_list
        }
        for f in rs.get("field", []):
            field_source = {
                "fileObject": { "@id": f"#{f.get('source_file')}" } if f.get('source_file') else None,
                "fileSet": { "@id": f"#{f.get('source_set')}" } if f.get('source_set') else None,
                "field": f.get("source_field"),
                "extract": {
                    "column": f.get("extract_column"),
                    "fileProperty": f.get("extract_property")
                }
            }
            # Clean up None values in source
            clean_source = {k: v for k, v in field_source.items() if v is not None}
            if "extract" in clean_source:
                extract_dict = clean_source["extract"]
                if isinstance(extract_dict, dict):
                    clean_extract = {k: v for k, v in extract_dict.items() if v is not None}
                    if clean_extract:
                        clean_source["extract"] = clean_extract
                    else:
                        clean_source.pop("extract", None)
            
            field = {
                "@type": "cr:Field",
                "name": f.get("name"),
                "dataType": f.get("dataType"),
                "source": clean_source
            }
            
            fields_list.append(field)
        
        record_set_list.append(record_set)
    
    # --- UNF Fingerprinting ---
    try:
        # Dynamically resolve skills directory (3 levels up from .gemini/skills/croissant_expert/scripts/)
        script_path_abs = os.path.abspath(__file__)
        skills_dir = os.path.dirname(os.path.dirname(os.path.dirname(script_path_abs)))
        unf_script_path = os.path.join(skills_dir, "unf", "scripts", "unf_hash.py")
        
        if os.path.exists(unf_script_path):
            import importlib.util
            spec = importlib.util.spec_from_file_location("unf_hash", unf_script_path)
            unf_module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(unf_module)
            
            # Compute UNF of the dataset dictionary
            dataset_unf = unf_module.compute_unf_json(dataset)
            if dataset_unf:
                dataset["sc:identifier"] = dataset_unf.replace("UNF:6:", "UNF6:")
    except Exception as e:
        print(f"Warning: Croissant fingerprinting failed: {e}")

    return dataset

def main():
    if len(sys.argv) < 2:
        print("Usage: python3 serialize.py <METADATA_JSON_FILE> [OUTPUT_FILE] [--nlp]")
        example = {
            "name": "Example Dataset",
            "description": "A simple example",
            "url": "https://example.com",
            "userQuery": "Optional query for session partitioning",
            "distribution": [{"name": "data-file", "contentUrl": "data.csv", "encodingFormat": "text/csv"}],
            "recordSet": [{"name": "main", "field": [{"name": "label", "dataType": "sc:Text", "source_file": "data-file", "extract_column": "label"}]}]
        }
        print("\nExample Input JSON:")
        print(json.dumps(example, indent=2))
        sys.exit(1)

    all_args = list(sys.argv)
    input_file = ""
    for i in range(1, len(all_args)):
        if not all_args[i].startswith("--"):
            input_file = all_args[i]
            break
            
    if not input_file or not os.path.exists(input_file):
        print(f"Error: Input file '{input_file}' not found.")
        sys.exit(1)

    apply_nlp = "--nlp" in sys.argv
    
    try:
        with open(input_file, 'r') as f:
            metadata = json.load(f)
        
        if apply_nlp:
            metadata["apply_nlp"] = True

        # Auto-resolve DATA_ROOT if query is provided
        query = metadata.get("userQuery")
        if query:
            try:
                script_dir = os.path.dirname(os.path.abspath(__file__))
                skills_dir = os.path.dirname(os.path.dirname(script_dir))
                unf_script = os.path.join(skills_dir, "unf", "scripts", "unf_hash.py")
                if os.path.exists(unf_script):
                    import importlib.util
                    spec = importlib.util.spec_from_file_location("unf_hash", unf_script)
                    unf_mod = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(unf_mod)
                    current_root = os.environ.get("DATA_ROOT", "data")
                    if current_root == "data":
                        partitioned_root = unf_mod.get_partitioned_root(query)
                        if partitioned_root != "data":
                            os.environ["DATA_ROOT"] = partitioned_root
            except Exception:
                pass

        data_root = os.environ.get("DATA_ROOT", "data")
        output_dir = os.path.join(data_root, "croissant")
        os.makedirs(output_dir, exist_ok=True)

        # --- Recursive Auto-detect of all artifacts in the partition ---
        dist_list = metadata.get("distribution", [])
        seen_files = {d.get("name") for d in dist_list}
        
        # Define subfolders to scan (all within data_root)
        folders_to_scan = ["nlp", "transcripts", "metadata", "cdif", "variables", "graph", "croissant"]
        
        for folder in folders_to_scan:
            folder_path = os.path.join(data_root, folder)
            if os.path.exists(folder_path):
                for f_name in os.listdir(folder_path):
                    if f_name.startswith(".") or f_name.endswith((".log", ".tmp")): continue
                    
                    full_path = os.path.abspath(os.path.join(folder_path, f_name))
                    if os.path.isdir(full_path): continue
                    
                    # Create a friendly name (e.g. nlp_entities, cdif_inventory, etc.)
                    if f_name.endswith(".entities.jsonld"): name = "nlp_entities"
                    elif f_name == "provenance.jsonld": name = "provenance_graph"
                    else: name = f"{folder}_{os.path.splitext(f_name)[0]}"
                    
                    if name not in seen_files:
                        # Try to get UNF
                        ent_unf = None
                        try:
                            if 'unf_mod' in locals():
                                ent_unf = unf_mod.compute_unf_file(full_path)
                                if ent_unf: ent_unf = ent_unf.replace("UNF:6:", "UNF6:")
                        except Exception: pass

                        encoding = "application/ld+json" if f_name.endswith((".jsonld", ".json")) else "text/plain"
                        if f_name.endswith(".txt"): encoding = "text/plain"
                        
                        dist_list.append({
                            "type": "FileObject",
                            "name": name,
                            "contentUrl": f"file://{full_path}",
                            "encodingFormat": encoding,
                            "unf": ent_unf
                        })
                        seen_files.add(name)
                        print(f"[Croissant] Auto-linked artifact: {folder}/{f_name} as '{name}'")
        
        metadata["distribution"] = dist_list

        output_file = ""
        for i in range(2, len(all_args)):
            arg_val = str(all_args[i])
            if not arg_val.startswith("--") and arg_val != input_file:
                output_file = arg_val
                break
        
        if output_file:
            if not os.path.dirname(output_file):
                output_file = os.path.join(output_dir, output_file)
        else:
            output_file = os.path.join(output_dir, "dataset-croissant.json")

        croissant_data = create_croissant_jsonld(metadata)
        with open(output_file, 'w') as f:
            json.dump(croissant_data, f, indent=2)
            
        print(f"Successfully serialized Croissant metadata to {output_file}")
        
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
