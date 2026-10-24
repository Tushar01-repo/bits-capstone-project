"""Live server using synthetic training fixtures for UI tests, not model quality."""
from tests.test_system import SystemTests

if __name__ == '__main__':
    SystemTests.setUpClass()
    print(SystemTests.base, flush=True)
    try:
        SystemTests.thread.join()
    except KeyboardInterrupt:
        pass
    finally:
        SystemTests.tearDownClass()
