"""Verify the deployed demo with credentials supplied through stdin, never CLI arguments."""
import json
import getpass
import sys
import httpx

def main():
    credentials = json.loads(getpass.getpass('Demo credentials JSON (hidden): '))
    base = sys.argv[1].rstrip('/')
    result = {'backend': base, 'steps': []}
    with httpx.Client(base_url=base, timeout=180) as client:
        def checked(method, path, expected=200, **kwargs):
            response = client.request(method, path, **kwargs)
            if response.status_code != expected:
                raise RuntimeError(f'{method} {path}: expected {expected}, received {response.status_code}')
            result['steps'].append({'method': method, 'path': path, 'status': response.status_code})
            print(f'{method} {path}: {response.status_code}', flush=True)
            return response
        checked('GET', '/health')
        checked('GET', '/customers', expected=401)
        preflight = checked('OPTIONS', '/customers', headers={'Origin': 'https://retainiq-ai.vercel.app', 'Access-Control-Request-Method': 'GET', 'Access-Control-Request-Headers': 'authorization'})
        assert preflight.headers['access-control-allow-origin'] == 'https://retainiq-ai.vercel.app'
        login = checked('POST', '/auth/login', json={'email': credentials['email'], 'password': credentials['password']}).json()
        client.headers['Authorization'] = 'Bearer ' + login['access_token']
        checked('GET', '/auth/me')
        dataset = checked('POST', '/data/demo', expected=201).json()
        trained = checked('POST', '/churn/train', json={'dataset_id': dataset['dataset_id']}).json()
        predictions = checked('POST', '/churn/predict/batch', json={}).json()
        assert predictions['count'] == 360
        high = checked('GET', '/churn/high-risk').json()['customers']
        cid = high[0]['customer_id'] if high else predictions['items'][0]['customer_id']
        checked('GET', '/explainability/global')
        explanation = checked('GET', '/explainability/customer/' + cid).json()
        assert explanation['method'].startswith('SHAP') and explanation['factors']
        checked('POST', '/segmentation/run')
        execution = checked('POST', '/agents/run', json={'customer_id': cid}).json()
        assert execution['status'] == 'awaiting_review'
        assistant = checked('POST', '/assistant/query', json={'customer_id': cid, 'question': 'Why is this customer at risk?'}).json()
        assert assistant['evidence'][0]['tool'] == 'explain_customer_prediction'
        report = checked('POST', '/reports/generate', expected=201, json={'title': 'Hosted synthetic demo verification'}).json()
        checked('GET', f'/reports/{report["id"]}/export?format=csv')
        analytics = checked('GET', '/analytics').json()
        assert analytics['total_customers'] == 360 and analytics['scored_customers'] == 360
        assert analytics['sources'] == ['synthetic demo']
        result.update({'selected_model': trained['selected_model'], 'model_version': trained['model_version'], 'held_out_test': trained['test'], 'customers': 360, 'scored_customers': 360, 'agent_status': execution['status'], 'customer_id': cid, 'execution_id': execution['execution_id'], 'report_id': report['id'], 'observed_campaign_outcomes_created': 0})
    print('RESULT=' + json.dumps(result), flush=True)

if __name__ == '__main__':
    main()
