# Contract Approval Testing Scripts

This directory contains scripts to test the complete contract approval flow, including integration with the Link2Prisma service for Dimona declarations.

## Overview

The scripts create a mock job, assign a worker with a specific SSN (04042306169) to it, and then test the ContractService approval process. This verifies that:

1. Worker profile completion validation works ✅
2. Job application creation works ✅
3. ContractService approval process works ✅
4. Link2Prisma integration for Dimona declarations works ⚠️ (API endpoints may need adjustment)
5. Distance calculation between addresses works ✅
6. Full end-to-end workflow integration ✅

## ✅ **VERIFIED WORKING**

The core functionality has been successfully tested and verified:
- **Worker Profile Validation**: 100% completion check works
- **Job Creation**: Mock jobs created successfully
- **Application Process**: Job applications created and linked properly
- **Approval Workflow**: ContractService.approve_application() works perfectly
- **Distance Calculation**: Automatic distance calculation between worker and job addresses
- **Database Integration**: All models and relationships work correctly

## Files

### 1. Management Command: `test_contract_approval.py`

A Django management command that can be run using `python manage.py`.

**Usage:**
```bash
# Test with default SSN (04042306169)
python manage.py test_contract_approval

# Test with specific SSN
python manage.py test_contract_approval --ssn 12345678901

# Test and cleanup afterwards
python manage.py test_contract_approval --cleanup

# Get help
python manage.py test_contract_approval --help
```

### 2. Standalone Script: `test_contract_flow.py`

A standalone Python script that can be run directly or imported as a module.

**Usage:**
```bash
# Run directly with default settings
python src/apps/legal/scripts/test_contract_flow.py

# Run with specific SSN
python src/apps/legal/scripts/test_contract_flow.py --ssn 12345678901

# Run without cleanup (keep test data)
python src/apps/legal/scripts/test_contract_flow.py --no-cleanup

# Get help
python src/apps/legal/scripts/test_contract_flow.py --help
```

**Import as module:**
```python
from apps.legal.scripts.test_contract_flow import test_contract_approval_flow

# Run test programmatically
results = test_contract_approval_flow(ssn='04042306169', cleanup=True)
print(results)
```

## What the Scripts Do

1. **Find Worker**: Look for an active worker with the specified SSN
2. **Check Profile**: Validate worker profile completion percentage
3. **Create Mock Data**:
   - Mock customer user
   - Mock job with realistic timing
   - Mock addresses for job and worker
4. **Create Application**: Create a job application linking worker to job
5. **Test Approval**: Use ContractService to approve the application
6. **Verify Integration**: Check that Link2Prisma Dimona declaration is created
7. **Display Results**: Show comprehensive test summary
8. **Cleanup**: Optionally remove all test data

## Expected Output

```
🔍 Looking for worker with SSN: 04042306169
✅ Found worker: John Doe (ID: abc-123-def)
📊 Worker profile completion: 100%
👤 Created mock customer: test_customer_1234567890@example.com
💼 Created mock job: Test Job for Contract Approval (ID: xyz-789-abc)
📍 Created worker address: Worker Street 456 2000 Antwerp
📝 Created job application (ID: def-456-ghi)
🚀 Testing ContractService approval...
✅ Application approved successfully!
📋 Application state: approved
🏛️  Dimona declaration should have been created in Link2Prisma

============================================================
📊 TEST SUMMARY
============================================================
Worker: John Doe
SSN: 04042306169
Worker Type: student
Job: Test Job for Contract Approval
Job State: pending
Application State: approved
Distance: 85.4 km
============================================================
🧹 Test data cleaned up
```

## Prerequisites

1. **Worker Exists**: A worker with SSN 04042306169 must exist in the database
2. **Profile Complete**: The worker's profile should be 100% complete for approval to succeed
3. **Link2Prisma Config**: Link2Prisma service must be properly configured
4. **Database Access**: Scripts need database write permissions

## Error Handling

The scripts handle various error scenarios:

- **Worker Not Found**: Clear error message if no worker with specified SSN exists
- **Incomplete Profile**: Shows completion percentage and missing fields
- **Approval Failures**: Catches and displays ContractService errors
- **Link2Prisma Issues**: Logs integration errors without failing the test
- **Cleanup Errors**: Handles cleanup failures gracefully

## Testing Different Scenarios

### Test with Incomplete Profile
```bash
# Find a worker with incomplete profile
python manage.py test_contract_approval --ssn <incomplete_worker_ssn>
```

### Test Without Cleanup (for debugging)
```bash
# Keep test data for manual inspection
python manage.py test_contract_approval --ssn 04042306169
```

### Test Multiple Workers
```bash
# Test different worker types
python manage.py test_contract_approval --ssn <student_ssn>
python manage.py test_contract_approval --ssn <freelancer_ssn>
python manage.py test_contract_approval --ssn <flexi_ssn>
```

## Integration with Existing Commands

These scripts complement the existing `fetch_prisma_workers` command:

```bash
# First, fetch worker data from Link2Prisma
python manage.py fetch_prisma_workers --ssn 04042306169

# Then test the approval flow
python manage.py test_contract_approval --ssn 04042306169
```

## Troubleshooting

### Common Issues

1. **Worker Not Found**
   - Verify the SSN exists in the database
   - Check that the worker is active
   - Ensure worker has a worker_profile

2. **Profile Incomplete**
   - Use WorkerUtil to check missing fields
   - Complete the profile before testing approval

3. **Link2Prisma Errors**
   - Check Link2Prisma configuration in settings
   - Verify certificate files are accessible
   - Test connection with `fetch_prisma_workers` first

4. **Permission Errors**
   - Ensure database write permissions
   - Check file system permissions for cleanup

### Debug Mode

For detailed debugging, you can modify the scripts to add more logging or run them in a Python shell:

```python
# In Django shell
from apps.legal.scripts.test_contract_flow import test_contract_approval_flow
results = test_contract_approval_flow(ssn='04042306169', cleanup=False)
# Inspect created objects manually