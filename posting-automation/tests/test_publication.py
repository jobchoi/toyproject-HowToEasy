from copy import deepcopy
import json
from pathlib import Path
import sys
import tempfile
import unittest
import zipfile
from xml.etree import ElementTree as ET
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import build_publication as publishing


class PublicationTests(unittest.TestCase):
    def setUp(self):
        self.story=publishing.PROJECT/'docs/publication/project-story.json'
        self.data=json.loads(self.story.read_text())

    def test_incomplete_story_cannot_be_ready_or_reference_private_files(self):
        data=deepcopy(self.data);data['publication_ready']=True
        with self.assertRaisesRegex(ValueError,'PUBLICATION_BLOCKED'):publishing.validate(data)
        for ref in ('../../etc/passwd','posting-automation/.local/raw-report.json'):
            data=deepcopy(self.data);data['claims'][0]['evidence']=[ref]
            with self.assertRaisesRegex(ValueError,'EVIDENCE_PATH'):publishing.validate(data)
        data=deepcopy(self.data);data['claims'][0]['text']='/home/private/server'
        with self.assertRaisesRegex(ValueError,'PRIVATE_METADATA'):publishing.validate(data)

    def test_outputs_preserve_boundaries_escape_markup_and_no_network(self):
        data=deepcopy(self.data);data['claims'][0]['text']='<script>alert(1)</script>'
        html,_=publishing.article(data)
        self.assertNotIn('<script>',html);self.assertIn('&lt;script&gt;',html)
        with tempfile.TemporaryDirectory() as folder:
            output=Path(folder)/'publication';result=publishing.build(self.story,output)
            self.assertFalse(result['published'])
            manifest=json.loads((output/'manifest.json').read_text())
            self.assertFalse(manifest['cloud_executed']);self.assertFalse(manifest['publication_ready'])
            script=(output/'ProjectStory.gs').read_text()
            self.assertNotIn('__POST_JSON__',script);self.assertIn('const PUBLICATION_READY = false;',script)
            self.assertIn('isDraft=true',script)
            body=(output/'tistory.html').read_text()
            self.assertIn('규칙 기반',body);self.assertIn('시간 초과',body)
            with self.assertRaises(FileExistsError):publishing.build(self.story,output)

    def test_all_claims_and_evidence_are_in_slide_data(self):
        slides=publishing.deck(publishing.validate(self.data))
        self.assertEqual(len(slides['slides']),len(self.data['claims'])+1)
        for claim,slide in zip(self.data['claims'],slides['slides'][1:]):
            self.assertIn(claim['id'],slide['tag']);self.assertEqual(claim['evidence'],slide['evidence'])

    def test_pptx_structure_if_optional_dependency_installed(self):
        try:import pptx
        except ImportError:self.skipTest('publication environment is optional')
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'story.pptx';data=publishing.deck(self.data)
            publishing.write_pptx(data,path)
            reread=pptx.Presentation(path)
            self.assertEqual(len(reread.slides),len(data['slides']))
            with zipfile.ZipFile(path) as archive:
                self.assertIsNone(archive.testzip())
                for name in archive.namelist():
                    if name.endswith('.xml'):ET.fromstring(archive.read(name))
