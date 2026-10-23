import test_web_app as fixtures
import json
from unittest import TestCase


class PlanApiTests(TestCase):
    setUp=fixtures.WebAppTests.setUp
    tearDown=fixtures.WebAppTests.tearDown
    request=fixtures.WebAppTests.request

    def test_revision_and_origin_checks_and_markdown_content_type(self):
        run='a'*32
        job={'id':run,'query':'synthetic','state':'done','created_at':'2026-10-23','result':{'answer':'fixture'}}
        self.manager.jobs[run]=job;self.manager._save(job)
        self.assertEqual(json.loads(self.request('GET','/api/plans/'+run)[1])['revision'],0)
        payload={'revision':0,'action':'upsert','items':[{'kind':'note','title':'성인2명'}]}
        self.assertEqual(self.request('POST','/api/plans/'+run,payload,headers={'Origin':'https://attacker.invalid'})[0],403)
        self.assertEqual(self.request('POST','/api/plans/'+run,payload)[0],200)
        self.assertEqual(self.request('POST','/api/plans/'+run,payload)[0],409)
        from http.client import HTTPConnection
        c=HTTPConnection('127.0.0.1',self.port,timeout=5)
        c.request('GET','/api/plans/'+run+'/markdown')
        r=c.getresponse();body=r.read().decode();c.close()
        self.assertEqual(r.status,200);self.assertIn('text/markdown',r.getheader('Content-Type'))
        self.assertIn('성인2명',body)
        self.assertEqual(self.request('GET','/api/plans/../../private')[0],404)
