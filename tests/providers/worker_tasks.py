# tests/providers/worker_tasks.py
"""
Worker task functions for MariaDB backend.

Features:
1. Module-level functions (pickle-able)
2. Parameters are fully serializable
3. Models configure their own connections inside the function
4. Disconnect after use
5. Both sync and async task functions supported
"""
from typing import Dict, Any, Optional
import importlib


def _find_async_backend(module_path, module, sync_class_name):
    """Locate ``Async<SyncName>`` for a backend whose classes span modules.

    ``impl.<backend>`` is a namespace package, so the sync and async classes no
    longer share a facade. Walk up from the module that defined the sync class
    until the async counterpart shows up, then fall back to the sync class.
    """
    wanted = f'Async{sync_class_name}'
    candidate = module
    name = module_path
    while candidate is not None:
        found = getattr(candidate, wanted, None)
        if found is not None:
            return found
        parent_name = name.rpartition('.')[0]
        if not parent_name or parent_name == name:
            break
        name = parent_name
        try:
            candidate = importlib.import_module(parent_name)
        except ImportError:
            break
    # The async class conventionally lives in the backend's own
    # ``async_backend`` module, which the upward walk cannot reach.
    parent_name = module_path.rpartition('.')[0]
    for candidate_name in (f'{parent_name}.async_backend',
                            f'{module_path.rsplit(".", 1)[0]}.async_backend'):
        try:
            sibling = importlib.import_module(candidate_name)
        except ImportError:
            continue
        found = getattr(sibling, wanted, None)
        if found is not None:
            return found
    return getattr(module, sync_class_name)


def _configure_model_from_params(params: dict, model_class) -> None:
    """
    Configure model from connection parameters.

    Args:
        params: Connection parameters provided by worker_connection_params fixture
        model_class: Model class to configure
    """
    # Dynamically import backend class
    backend_module = importlib.import_module(params['backend_module'])
    backend_class = getattr(backend_module, params['backend_class_name'])

    # Dynamically import config class
    config_module = importlib.import_module(params['config_module'])
    config_class = getattr(config_module, params['config_class_name'])

    # Extract configuration parameters (exclude business parameters)
    config_keys = {
        'host', 'port', 'database', 'username', 'password',
        'pool_size', 'pool_timeout', 'charset', 'timezone',
        'ssl_ca', 'ssl_cert', 'ssl_key', 'ssl_mode',
        'autocommit', 'auth_plugin', 'init_command',
        'driver_type', 'options'
    }
    config_dict = {k: v for k, v in params['config_dict'].items() if k in config_keys}

    config = config_class(**config_dict)

    # Configure model
    model_class.configure(config, backend_class)


async def _async_configure_model_from_params(params: dict, model_class) -> None:
    """
    Async configure model from connection parameters.

    Args:
        params: Connection parameters provided by worker_connection_params fixture
        model_class: Async model class to configure
    """
    # Dynamically import backend class
    backend_module = importlib.import_module(params['backend_module'])
    backend_class = getattr(backend_module, params['backend_class_name'])

    # Convert sync backend to async backend if needed
    # e.g., MariaDBBackend -> AsyncMariaDBBackend
    if not backend_class.__name__.startswith('Async'):
        backend_class = _find_async_backend(
            params['backend_module'], backend_module, backend_class.__name__
        )

    # Dynamically import config class
    config_module = importlib.import_module(params['config_module'])
    config_class = getattr(config_module, params['config_class_name'])

    # Extract configuration parameters (exclude business parameters)
    config_keys = {
        'host', 'port', 'database', 'username', 'password',
        'pool_size', 'pool_timeout', 'charset', 'timezone',
        'ssl_ca', 'ssl_cert', 'ssl_key', 'ssl_mode',
        'autocommit', 'auth_plugin', 'init_command',
        'driver_type', 'options'
    }
    config_dict = {k: v for k, v in params['config_dict'].items() if k in config_keys}

    config = config_class(**config_dict)

    # Configure async model (configure() is already an async method in AsyncBaseActiveRecord)
    await model_class.configure(config, backend_class)


def create_user_task(params: dict) -> Dict[str, Any]:
    """
    Create user task.

    Args:
        params: Dictionary containing connection parameters + business parameters
            - backend_module, backend_class_name, config_module, config_class_name, config_dict
            - username, email, age (optional)

    Returns:
        {'id': user_id, 'success': True} or {'error': str, 'success': False}
    """
    params = params.copy()

    username = params.pop('username')
    email = params.pop('email')
    age = params.pop('age', None)

    from rhosocial.activerecord.testsuite.feature.basic.fixtures.models import User

    _configure_model_from_params(params, User)

    try:
        user = User(username=username, email=email, age=age)
        user.save()
        return {'id': user.id, 'success': True}
    except Exception as e:
        return {'error': str(e), 'success': False}
    finally:
        User.backend().disconnect()


def read_user_task(params: dict) -> Dict[str, Any]:
    """
    Read user task.

    Args:
        params: Dictionary containing connection parameters + business parameters
            - backend_module, backend_class_name, config_module, config_class_name, config_dict
            - user_id

    Returns:
        {'id': ..., 'username': ..., 'email': ..., 'success': True}
        or {'error': str, 'success': False}
    """
    params = params.copy()

    user_id = params.pop('user_id')

    from rhosocial.activerecord.testsuite.feature.basic.fixtures.models import User

    _configure_model_from_params(params, User)

    try:
        user = User.find_one({'id': user_id})
        if user:
            return {
                'id': user.id,
                'username': user.username,
                'email': user.email,
                'age': user.age,
                'success': True
            }
        else:
            return {'error': 'User not found', 'success': False}
    except Exception as e:
        return {'error': str(e), 'success': False}
    finally:
        User.backend().disconnect()


def update_user_task(params: dict) -> Dict[str, Any]:
    """
    Update user task.

    Args:
        params: Dictionary containing connection parameters + business parameters
            - backend_module, backend_class_name, config_module, config_class_name, config_dict
            - user_id
            - age, username, email etc. (optional update fields)

    Returns:
        {'id': ..., 'success': True} or {'error': str, 'success': False}
    """
    params = params.copy()

    user_id = params.pop('user_id')

    from rhosocial.activerecord.testsuite.feature.basic.fixtures.models import User

    _configure_model_from_params(params, User)

    try:
        user = User.find_one({'id': user_id})
        if not user:
            return {'error': 'User not found', 'success': False}

        if 'age' in params:
            user.age = params['age']
        if 'username' in params:
            user.username = params['username']
        if 'email' in params:
            user.email = params['email']

        user.save()
        return {'id': user.id, 'success': True}
    except Exception as e:
        return {'error': str(e), 'success': False}
    finally:
        User.backend().disconnect()


def delete_user_task(params: dict) -> Dict[str, Any]:
    """
    Delete user task.

    Args:
        params: Dictionary containing connection parameters + business parameters
            - backend_module, backend_class_name, config_module, config_class_name, config_dict
            - user_id

    Returns:
        {'success': True} or {'error': str, 'success': False}
    """
    params = params.copy()

    user_id = params.pop('user_id')

    from rhosocial.activerecord.testsuite.feature.basic.fixtures.models import User

    _configure_model_from_params(params, User)

    try:
        user = User.find_one({'id': user_id})
        if not user:
            return {'error': 'User not found', 'success': False}

        user.delete()
        return {'success': True}
    except Exception as e:
        return {'error': str(e), 'success': False}
    finally:
        User.backend().disconnect()


# ── Async Task Functions ──────────────────────────────────────────────────────
# These async functions demonstrate AsyncActiveRecord usage in WorkerPool.
# WorkerPool automatically detects async functions and runs them with asyncio.run().


async def async_create_user_task(params: dict) -> Dict[str, Any]:
    """
    Async create user task using AsyncActiveRecord.

    Args:
        params: Dictionary containing connection parameters + business parameters
            - backend_module, backend_class_name, config_module, config_class_name, config_dict
            - username, email, age (optional)

    Returns:
        {'id': user_id, 'success': True} or {'error': str, 'success': False}
    """
    params = params.copy()

    username = params.pop('username')
    email = params.pop('email')
    age = params.pop('age', None)

    from rhosocial.activerecord.testsuite.feature.basic.fixtures.models import AsyncUser

    await _async_configure_model_from_params(params, AsyncUser)

    try:
        user = AsyncUser(username=username, email=email, age=age)
        await user.save()
        return {'id': user.id, 'success': True}
    except Exception as e:
        return {'error': str(e), 'success': False}
    finally:
        await AsyncUser.backend().disconnect()


async def async_read_user_task(params: dict) -> Dict[str, Any]:
    """
    Async read user task using AsyncActiveRecord.

    Args:
        params: Dictionary containing connection parameters + business parameters
            - backend_module, backend_class_name, config_module, config_class_name, config_dict
            - user_id

    Returns:
        {'id': ..., 'username': ..., 'email': ..., 'success': True}
        or {'error': str, 'success': False}
    """
    params = params.copy()

    user_id = params.pop('user_id')

    from rhosocial.activerecord.testsuite.feature.basic.fixtures.models import AsyncUser

    await _async_configure_model_from_params(params, AsyncUser)

    try:
        user = await AsyncUser.find_one({'id': user_id})
        if user:
            return {
                'id': user.id,
                'username': user.username,
                'email': user.email,
                'age': user.age,
                'success': True
            }
        else:
            return {'error': 'User not found', 'success': False}
    except Exception as e:
        return {'error': str(e), 'success': False}
    finally:
        await AsyncUser.backend().disconnect()


async def async_update_user_task(params: dict) -> Dict[str, Any]:
    """
    Async update user task using AsyncActiveRecord.

    Args:
        params: Dictionary containing connection parameters + business parameters
            - backend_module, backend_class_name, config_module, config_class_name, config_dict
            - user_id
            - age, username, email etc. (optional update fields)

    Returns:
        {'id': ..., 'success': True} or {'error': str, 'success': False}
    """
    params = params.copy()

    user_id = params.pop('user_id')

    from rhosocial.activerecord.testsuite.feature.basic.fixtures.models import AsyncUser

    await _async_configure_model_from_params(params, AsyncUser)

    try:
        user = await AsyncUser.find_one({'id': user_id})
        if not user:
            return {'error': 'User not found', 'success': False}

        if 'age' in params:
            user.age = params['age']
        if 'username' in params:
            user.username = params['username']
        if 'email' in params:
            user.email = params['email']

        await user.save()
        return {'id': user.id, 'success': True}
    except Exception as e:
        return {'error': str(e), 'success': False}
    finally:
        await AsyncUser.backend().disconnect()


async def async_delete_user_task(params: dict) -> Dict[str, Any]:
    """
    Async delete user task using AsyncActiveRecord.

    Args:
        params: Dictionary containing connection parameters + business parameters
            - backend_module, backend_class_name, config_module, config_class_name, config_dict
            - user_id

    Returns:
        {'success': True} or {'error': str, 'success': False}
    """
    params = params.copy()

    user_id = params.pop('user_id')

    from rhosocial.activerecord.testsuite.feature.basic.fixtures.models import AsyncUser

    await _async_configure_model_from_params(params, AsyncUser)

    try:
        user = await AsyncUser.find_one({'id': user_id})
        if not user:
            return {'error': 'User not found', 'success': False}

        await user.delete()
        return {'success': True}
    except Exception as e:
        return {'error': str(e), 'success': False}
    finally:
        await AsyncUser.backend().disconnect()
