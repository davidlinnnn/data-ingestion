"""Atomic same-source group assembly; source refs never target a mutated graph."""
from copy import deepcopy
import method as m


def apply_groups(raw, members):
    if not members:
        raise ValueError("empty source-group batch")
    pages=set();views={};images={};kept=[];actions=[];records=[]
    owners=set()
    for bound,response in members:
        # Validate each response against its original scope before mechanical joining.
        m.apply(raw,bound,response)
        current=set(bound["text_candidates"])
        if owners & current:
            raise ValueError("overlapping source-group owner")
        owners |= current
        pages.update(bound["pages"])
        for view in bound["views"]:
            page=view["page_no"]
            if page in views and views[page]!=view:
                raise ValueError("conflicting source page view")
            views[page]=deepcopy(view)
        for image in bound["images"]:
            key=image["image_key"]
            if key in images and images[key]!=image:
                raise ValueError("conflicting original image")
            images[key]=deepcopy(image)
        prefix=m.digest(bound)
        kept.extend(response["keep"])
        for original in response["actions"]:
            value=deepcopy(original);value["id"]=prefix+":"+value["id"];actions.append(value)
        records.append({"scope":deepcopy(bound),"raw_response":deepcopy(response)})
    combined=m.bind(raw,sorted(pages),[views[p] for p in sorted(views)],list(images.values()),"A")
    result=m.apply(raw,combined,{"group_sha256":m.digest(combined),"keep":kept,"actions":actions})
    result["binding"]["member_transports"]=records
    return result
