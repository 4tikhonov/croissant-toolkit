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
        """Robust check for duplicates in a list of multilingual dicts or strings."""
        val_to_check = item_val["@value"] if isinstance(item_val, dict) else str(item_val)
        for c in collection:
            c_val = c["@value"] if isinstance(c, dict) else str(c)
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
                "sha256": dist.get("sha256")
            }
        elif dist_type == "FileSet":
            obj = {
                "@type": "cr:FileSet",
                "name": dist.get("name"),
                "containedIn": dist.get("containedIn"),
                "encodingFormat": dist.get("encodingFormat"),
                "includes": dist.get("includes")
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

    return dataset

def main():
    if len(sys.argv) < 2:
        print("Usage: python3 serialize.py <METADATA_JSON_FILE> [OUTPUT_FILE]")
        # Example metadata structure
        example = {
            "name": "Example Dataset",
            "description": "A simple example",
            "url": "https://example.com",
            "distribution": [
                {"name": "data-file", "contentUrl": "data.csv", "encodingFormat": "text/csv"}
            ],
            "recordSet": [
                {
                    "name": "main",
                    "field": [
                        {"name": "label", "dataType": "sc:Text", "source_file": "data-file", "extract_column": "label"}
                    ]
                }
            ]
        }
        print("\nExample Input JSON:")
        print(json.dumps(example, indent=2))
        sys.exit(1)

    input_file = sys.argv[1]
    output_dir = "data/croissant"
    os.makedirs(output_dir, exist_ok=True)
    
    apply_nlp = "--nlp" in sys.argv
    
    all_args = list(sys.argv)
    output_file = ""
    for i in range(2, len(all_args)):
        arg_val = str(all_args[i])
        if not arg_val.startswith("--"):
            output_file = arg_val
            break
    
    if output_file:
        # If user provides a filename without a path, put it in the default dir
        if not os.path.dirname(output_file):
            output_file = os.path.join(output_dir, output_file)
    else:
        output_file = os.path.join(output_dir, "dataset-croissant.json")

    try:
        with open(input_file, 'r') as f:
            metadata = json.load(f)
        
        if apply_nlp:
            metadata["apply_nlp"] = True
            
        croissant_data = create_croissant_jsonld(metadata)
        
        with open(output_file, 'w') as f:
            json.dump(croissant_data, f, indent=2)
            
        print(f"Successfully serialized Croissant metadata to {output_file}")
        
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
