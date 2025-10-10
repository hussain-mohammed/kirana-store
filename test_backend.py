import requests

print('Testing local backend...')
response = requests.get('http://localhost:8000/products')
print(f'Status: {response.status_code}')

if response.status_code == 200:
    data = response.json()
    print(f'Products count: {len(data)}')
    if data:
        print(f'First product: {data[0]}')
    else:
        print('No products found')
else:
    print(f'Error: {response.text}')
