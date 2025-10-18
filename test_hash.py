import bcrypt

# Test if admin123 matches the hash
stored_hash = '$2b$12$vFYo5NA/twx6Fg8l4qgpGexR/xlc4AXnqRW0AfqK9HPrPtokq8SFK'

password = 'admin123'
if bcrypt.checkpw(password.encode('utf-8'), stored_hash.encode('utf-8')):
    print("✅ Password admin123 matches the hash")
else:
    print("❌ Password admin123 does not match the hash")

# Test with 123456
password2 = '123456'
if bcrypt.checkpw(password2.encode('utf-8'), stored_hash.encode('utf-8')):
    print("✅ Password 123456 matches the hash")
else:
    print("❌ Password 123456 does not match the hash")

# Check what the hash of admin123 would be
new_hash = bcrypt.hashpw('admin123'.encode('utf-8'), bcrypt.gensalt())
print(f"Hash of admin123: {new_hash.decode('utf-8')}")
