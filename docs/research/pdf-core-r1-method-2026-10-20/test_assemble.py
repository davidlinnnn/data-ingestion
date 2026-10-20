from copy import deepcopy
import unittest
import method as m
import test_method as t
from assemble import apply_groups
from docling_core.types.doc import DocItemLabel
from markdown_it import MarkdownIt


class AssemblyControls(unittest.TestCase):
    def members(self):
        doc=t.document();first=doc.add_text(label=DocItemLabel.TEXT,text="first",prov=t.prov(1))
        last=doc.add_text(label=DocItemLabel.TEXT,text="last",prov=t.prov(2))
        values=[]
        for page,item,text in ((1,first,"PAGE_ONE"),(2,last,"PAGE_TWO")):
            bound=t.bound(doc,pages=(page,))
            action=t.action([item.self_ref],item.self_ref,[t.block(text)]);action["source_pages"]=[page]
            values.append((bound,t.response(bound,[action])))
        return t.raw(doc),values

    def test_two_original_ref_groups_survive_public_ref_renumbering(self):
        raw,members=self.members();result=apply_groups(raw,members)
        rendered=MarkdownIt().render(result["markdown"])
        self.assertLess(rendered.index("PAGE_ONE"),rendered.index("PAGE_TWO"))
        self.assertEqual(len(result["binding"]["member_transports"]),2)

    def test_member_arrival_order_does_not_reorder_source(self):
        raw,members=self.members()
        self.assertEqual(apply_groups(raw,members)["markdown"],apply_groups(raw,members[::-1])["markdown"])

    def test_overlapping_member_and_foreign_response_are_rejected(self):
        raw,members=self.members()
        with self.assertRaisesRegex(ValueError,"overlapping"):
            apply_groups(raw,[members[0],members[0]])
        changed=deepcopy(members);changed[0][1]["group_sha256"]="foreign"
        with self.assertRaisesRegex(ValueError,"foreign"):
            apply_groups(raw,changed)

    def test_original_member_payloads_remain_immutable(self):
        raw,members=self.members();before=deepcopy(members)
        apply_groups(raw,members)
        self.assertEqual(members,before)


if __name__=="__main__":unittest.main()
