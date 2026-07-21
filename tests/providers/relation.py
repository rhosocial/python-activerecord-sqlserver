# tests/providers/relation.py
from typing import Dict, List, Tuple, Type, Set

from rhosocial.activerecord.model import ActiveRecord, AsyncActiveRecord
from rhosocial.activerecord.backend.impl.sqlserver import AsyncSQLServerBackend
from rhosocial.activerecord.testsuite.feature.relation.interfaces import (
    IRelationSyncProvider,
    IRelationAsyncProvider,
)
from rhosocial.activerecord.testsuite.feature.relation.fixtures.models import (
    Employee,
    Department,
    Author,
    Book,
    Chapter,
    Profile,
    User,
    Post,
    Comment,
    AsyncUser,
    AsyncPost,
    AsyncComment,
    BoundaryOwner,
    BoundaryProfile,
    BoundaryPost,
    AsyncBoundaryOwner,
    AsyncBoundaryProfile,
    AsyncBoundaryPost,
)
from .scenarios import get_enabled_scenarios, get_scenario


EMPLOYEE_DEPARTMENT_SCHEMA = """
    CREATE TABLE IF NOT EXISTS departments (
        id INT AUTO_INCREMENT PRIMARY KEY,
        name VARCHAR(255) NOT NULL,
        description TEXT
    );
    CREATE TABLE IF NOT EXISTS employees (
        id INT AUTO_INCREMENT PRIMARY KEY,
        username VARCHAR(255) NOT NULL,
        department_id INT NOT NULL
    );
    DELETE FROM employees;
    DELETE FROM departments;
"""

AUTHOR_BOOK_SCHEMA = """
    CREATE TABLE IF NOT EXISTS authors (
        id INT AUTO_INCREMENT PRIMARY KEY,
        name VARCHAR(255) NOT NULL
    );
    CREATE TABLE IF NOT EXISTS books (
        id INT AUTO_INCREMENT PRIMARY KEY,
        title VARCHAR(255) NOT NULL,
        author_id INT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS chapters (
        id INT AUTO_INCREMENT PRIMARY KEY,
        title VARCHAR(255) NOT NULL,
        book_id INT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS profiles (
        id INT AUTO_INCREMENT PRIMARY KEY,
        bio TEXT NOT NULL,
        author_id INT NOT NULL
    );
    DELETE FROM chapters;
    DELETE FROM books;
    DELETE FROM profiles;
    DELETE FROM authors;
"""

USER_POST_COMMENT_SCHEMA = """
    CREATE TABLE IF NOT EXISTS users (
        id INT AUTO_INCREMENT PRIMARY KEY,
        name VARCHAR(255) NOT NULL,
        email VARCHAR(255),
        settings JSON
    );
    CREATE TABLE IF NOT EXISTS posts (
        id INT AUTO_INCREMENT PRIMARY KEY,
        title VARCHAR(255) NOT NULL,
        body TEXT NOT NULL,
        user_id INT NOT NULL,
        view_count INT NOT NULL DEFAULT 0,
        metadata JSON
    );
    CREATE TABLE IF NOT EXISTS comments (
        id INT AUTO_INCREMENT PRIMARY KEY,
        body TEXT NOT NULL,
        post_id INT NOT NULL,
        meta JSON
    );
    DELETE FROM comments;
    DELETE FROM posts;
    DELETE FROM users;
"""

RELATION_BOUNDARY_SCHEMA = """
    CREATE TABLE IF NOT EXISTS relation_boundary_owners (
        id INT AUTO_INCREMENT PRIMARY KEY,
        name VARCHAR(255) NOT NULL
    );
    CREATE TABLE IF NOT EXISTS relation_boundary_profiles (
        id INT AUTO_INCREMENT PRIMARY KEY,
        bio TEXT NOT NULL,
        owner_id INT NULL
    );
    CREATE TABLE IF NOT EXISTS relation_boundary_posts (
        id INT AUTO_INCREMENT PRIMARY KEY,
        title VARCHAR(255) NOT NULL,
        owner_id INT NULL
    );
    DELETE FROM relation_boundary_posts;
    DELETE FROM relation_boundary_profiles;
    DELETE FROM relation_boundary_owners;
"""


class RelationProviderBase:
    def __init__(self):
        self._scenario_db_files: Dict[str, List[str]] = {}
        self._created_tables: Set[str] = set()

    def get_test_scenarios(self) -> List[str]:
        from rhosocial.activerecord.backend.impl.sqlserver.dialect import SQLServerDialect
        scenarios = []
        for name in get_enabled_scenarios().keys():
            try:
                backend_class, config = get_scenario(name)
                backend = backend_class(connection_config=config)
                backend.connect()
                version = backend.get_server_version()
                backend.disconnect()
                dialect = SQLServerDialect(version)
                if not dialect.supports_json_type():
                    continue
            except Exception:
                pass
            scenarios.append(name)
        return scenarios

    def _configure_with_shared_backend(self, model_class, config, backend_class, backend):
        model_class.__connection_config__ = config
        model_class.__backend_class__ = backend_class
        model_class.__backend__ = backend


class RelationSyncProvider(RelationProviderBase, IRelationSyncProvider):
    def __init__(self):
        super().__init__()
        self._active_backends = []
        self._sync_user_post_comment_setup = False
        self._sync_relation_boundary_setup = False

    def _execute_script(self, backend, sql: str):
        for statement in sql.split(";"):
            statement = statement.strip()
            if statement:
                backend.execute(statement)

    def _setup_employee_department(self, scenario_name):
        backend_class, config = get_scenario(scenario_name)
        Employee.configure(config, backend_class)
        backend = Employee.backend()
        backend.connect()
        backend.introspect_and_adapt()
        self._active_backends.append(backend)
        self._execute_script(backend, EMPLOYEE_DEPARTMENT_SCHEMA)
        self._configure_with_shared_backend(Department, config, backend_class, backend)
        self._created_tables.update(["employees", "departments"])
        return Employee, Department

    def _setup_author_book(self, scenario_name):
        backend_class, config = get_scenario(scenario_name)
        Author.configure(config, backend_class)
        backend = Author.backend()
        backend.connect()
        backend.introspect_and_adapt()
        self._active_backends.append(backend)
        self._execute_script(backend, AUTHOR_BOOK_SCHEMA)
        self._configure_with_shared_backend(Book, config, backend_class, backend)
        self._configure_with_shared_backend(Chapter, config, backend_class, backend)
        self._configure_with_shared_backend(Profile, config, backend_class, backend)
        self._created_tables.update(["authors", "books", "chapters", "profiles"])
        return Author, Book, Chapter, Profile

    def _setup_user_post_comment_sync(self, scenario_name):
        if not self._sync_user_post_comment_setup:
            backend_class, config = get_scenario(scenario_name)
            User.configure(config, backend_class)
            backend = User.backend()
            backend.connect()
            backend.introspect_and_adapt()
            self._active_backends.append(backend)
            self._execute_script(backend, USER_POST_COMMENT_SCHEMA)
            self._configure_with_shared_backend(Post, config, backend_class, backend)
            self._configure_with_shared_backend(Comment, config, backend_class, backend)
            self._sync_user_post_comment_setup = True
            self._created_tables.update(["users", "posts", "comments"])

    def _setup_relation_boundary_sync(self, scenario_name):
        if not self._sync_relation_boundary_setup:
            backend_class, config = get_scenario(scenario_name)
            BoundaryOwner.configure(config, backend_class)
            backend = BoundaryOwner.backend()
            backend.connect()
            backend.introspect_and_adapt()
            self._active_backends.append(backend)
            self._execute_script(backend, RELATION_BOUNDARY_SCHEMA)
            self._configure_with_shared_backend(
                BoundaryProfile,
                config,
                backend_class,
                backend,
            )
            self._configure_with_shared_backend(
                BoundaryPost,
                config,
                backend_class,
                backend,
            )
            self._sync_relation_boundary_setup = True
            self._created_tables.update(
                ["relation_boundary_owners", "relation_boundary_profiles", "relation_boundary_posts"]
            )

    def setup_employee_department_fixtures(
        self,
        scenario_name: str,
    ) -> Tuple[Type[ActiveRecord], Type[ActiveRecord]]:
        return self._setup_employee_department(scenario_name)

    def setup_author_book_fixtures(
        self,
        scenario_name: str,
    ) -> Tuple[
        Type[ActiveRecord],
        Type[ActiveRecord],
        Type[ActiveRecord],
        Type[ActiveRecord],
    ]:
        return self._setup_author_book(scenario_name)

    def setup_user_model(self, scenario_name: str) -> Type[ActiveRecord]:
        self._setup_user_post_comment_sync(scenario_name)
        return User

    def setup_post_model(self, scenario_name: str) -> Type[ActiveRecord]:
        self._setup_user_post_comment_sync(scenario_name)
        return Post

    def setup_comment_model(self, scenario_name: str) -> Type[ActiveRecord]:
        self._setup_user_post_comment_sync(scenario_name)
        return Comment

    def setup_relation_boundary_fixtures(
        self,
        scenario_name: str,
    ) -> Tuple[Type[ActiveRecord], Type[ActiveRecord], Type[ActiveRecord]]:
        self._setup_relation_boundary_sync(scenario_name)
        return BoundaryOwner, BoundaryProfile, BoundaryPost

    def load_relation_boundary_dataset(self, scenario_name: str, dataset_name: str) -> Dict[str, int]:
        self._setup_relation_boundary_sync(scenario_name)
        return self._load_relation_boundary_dataset(dataset_name)

    def _load_relation_boundary_dataset(self, dataset_name):
        if dataset_name == "null_foreign_key":
            profile = BoundaryProfile(bio="No owner", owner_id=None)
            profile.save()
            return {"profile_id": profile.id}

        if dataset_name == "orphan_foreign_key":
            missing_owner_id = 999999
            post = BoundaryPost(title="Orphan post", owner_id=missing_owner_id)
            post.save()
            return {"post_id": post.id, "missing_owner_id": missing_owner_id}

        if dataset_name == "owner_without_children":
            owner = BoundaryOwner(name="Owner without children")
            owner.save()
            return {"owner_id": owner.id}

        if dataset_name == "multiple_has_one_matches":
            owner = BoundaryOwner(name="Owner with duplicate profiles")
            owner.save()
            first = BoundaryProfile(bio="First profile", owner_id=owner.id)
            first.save()
            second = BoundaryProfile(bio="Second profile", owner_id=owner.id)
            second.save()
            return {
                "owner_id": owner.id,
                "first_profile_id": first.id,
                "second_profile_id": second.id,
            }

        raise ValueError(f"Unknown relation boundary dataset: {dataset_name}")

    def _reset_sync_setup_state(self):
        self._sync_user_post_comment_setup = False
        self._sync_relation_boundary_setup = False

    def cleanup_after_test(self, scenario_name: str) -> None:
        for backend in self._active_backends:
            try:
                if self._created_tables:
                    backend.execute("SET FOREIGN_KEY_CHECKS = 0")
                    for table in list(self._created_tables):
                        try:
                            backend.execute(f"DROP TABLE IF EXISTS `{table}`")
                        except Exception:
                            pass
                    backend.execute("SET FOREIGN_KEY_CHECKS = 1")
            except Exception:
                try:
                    backend.execute("SET FOREIGN_KEY_CHECKS = 1")
                except Exception:
                    pass
            finally:
                try:
                    backend.disconnect()
                except Exception:
                    pass
        self._active_backends.clear()
        self._created_tables.clear()
        self._reset_sync_setup_state()


class RelationAsyncProvider(RelationProviderBase, IRelationAsyncProvider):
    def __init__(self):
        super().__init__()
        self._active_async_backends = []
        self._async_user_post_comment_setup = False
        self._async_relation_boundary_setup = False

    async def _execute_script_async(self, backend, sql: str):
        for statement in sql.split(";"):
            statement = statement.strip()
            if statement:
                await backend.execute(statement)

    def _configure_async_model_without_connection(self, model_class, config, backend=None):
        if backend is None:
            backend = AsyncSQLServerBackend(connection_config=config)
        model_class.__connection_config__ = config
        model_class.__backend_class__ = AsyncSQLServerBackend
        model_class.__backend__ = backend
        return backend

    async def _setup_employee_department_async(self, scenario_name):
        _, config = get_scenario(scenario_name)
        backend = self._configure_async_model_without_connection(Employee, config)
        self._configure_async_model_without_connection(Department, config, backend)
        self._active_async_backends.append(backend)
        await backend.connect()
        await backend.introspect_and_adapt()
        await self._execute_script_async(backend, EMPLOYEE_DEPARTMENT_SCHEMA)
        self._created_tables.update(["employees", "departments"])
        return Employee, Department

    async def _setup_author_book_async(self, scenario_name):
        _, config = get_scenario(scenario_name)
        backend = self._configure_async_model_without_connection(Author, config)
        self._configure_async_model_without_connection(Book, config, backend)
        self._configure_async_model_without_connection(Chapter, config, backend)
        self._configure_async_model_without_connection(Profile, config, backend)
        self._active_async_backends.append(backend)
        await backend.connect()
        await backend.introspect_and_adapt()
        await self._execute_script_async(backend, AUTHOR_BOOK_SCHEMA)
        self._created_tables.update(["authors", "books", "chapters", "profiles"])
        return Author, Book, Chapter, Profile

    async def _setup_user_post_comment_async(self, scenario_name):
        if not self._async_user_post_comment_setup:
            _, config = get_scenario(scenario_name)
            backend = self._configure_async_model_without_connection(AsyncUser, config)
            self._configure_async_model_without_connection(AsyncPost, config, backend)
            self._configure_async_model_without_connection(AsyncComment, config, backend)
            self._active_async_backends.append(backend)
            await backend.connect()
            await backend.introspect_and_adapt()
            await self._execute_script_async(backend, USER_POST_COMMENT_SCHEMA)
            self._async_user_post_comment_setup = True
            self._created_tables.update(["users", "posts", "comments"])

    async def _setup_relation_boundary_async(self, scenario_name):
        if not self._async_relation_boundary_setup:
            _, config = get_scenario(scenario_name)
            backend = self._configure_async_model_without_connection(
                AsyncBoundaryOwner,
                config,
            )
            self._configure_async_model_without_connection(
                AsyncBoundaryProfile,
                config,
                backend,
            )
            self._configure_async_model_without_connection(
                AsyncBoundaryPost,
                config,
                backend,
            )
            self._active_async_backends.append(backend)
            await backend.connect()
            await backend.introspect_and_adapt()
            await self._execute_script_async(backend, RELATION_BOUNDARY_SCHEMA)
            self._created_tables.update(
                ["relation_boundary_owners", "relation_boundary_profiles", "relation_boundary_posts"]
            )
            self._async_relation_boundary_setup = True

    async def setup_employee_department_fixtures(
        self,
        scenario_name: str,
    ) -> Tuple[Type[ActiveRecord], Type[ActiveRecord]]:
        return await self._setup_employee_department_async(scenario_name)

    async def setup_author_book_fixtures(
        self,
        scenario_name: str,
    ) -> Tuple[
        Type[ActiveRecord],
        Type[ActiveRecord],
        Type[ActiveRecord],
        Type[ActiveRecord],
    ]:
        return await self._setup_author_book_async(scenario_name)

    async def setup_user_model(self, scenario_name: str) -> Type[ActiveRecord]:
        await self._setup_user_post_comment_async(scenario_name)
        return AsyncUser

    async def setup_post_model(self, scenario_name: str) -> Type[ActiveRecord]:
        await self._setup_user_post_comment_async(scenario_name)
        return AsyncPost

    async def setup_comment_model(self, scenario_name: str) -> Type[ActiveRecord]:
        await self._setup_user_post_comment_async(scenario_name)
        return AsyncComment

    async def setup_relation_boundary_fixtures(
        self,
        scenario_name: str,
    ) -> Tuple[Type[AsyncActiveRecord], Type[AsyncActiveRecord], Type[AsyncActiveRecord]]:
        await self._setup_relation_boundary_async(scenario_name)
        return AsyncBoundaryOwner, AsyncBoundaryProfile, AsyncBoundaryPost

    async def load_relation_boundary_dataset(
        self,
        scenario_name: str,
        dataset_name: str,
    ) -> Dict[str, int]:
        await self._setup_relation_boundary_async(scenario_name)
        return await self._load_async_relation_boundary_dataset(dataset_name)

    async def _load_async_relation_boundary_dataset(self, dataset_name):
        if dataset_name == "null_foreign_key":
            profile = AsyncBoundaryProfile(bio="No owner", owner_id=None)
            await profile.save()
            return {"profile_id": profile.id}

        if dataset_name == "orphan_foreign_key":
            missing_owner_id = 999999
            post = AsyncBoundaryPost(title="Orphan post", owner_id=missing_owner_id)
            await post.save()
            return {"post_id": post.id, "missing_owner_id": missing_owner_id}

        if dataset_name == "owner_without_children":
            owner = AsyncBoundaryOwner(name="Owner without children")
            await owner.save()
            return {"owner_id": owner.id}

        if dataset_name == "multiple_has_one_matches":
            owner = AsyncBoundaryOwner(name="Owner with duplicate profiles")
            await owner.save()
            first = AsyncBoundaryProfile(bio="First profile", owner_id=owner.id)
            await first.save()
            second = AsyncBoundaryProfile(bio="Second profile", owner_id=owner.id)
            await second.save()
            return {
                "owner_id": owner.id,
                "first_profile_id": first.id,
                "second_profile_id": second.id,
            }

        raise ValueError(f"Unknown relation boundary dataset: {dataset_name}")

    def _reset_async_setup_state(self):
        self._async_user_post_comment_setup = False
        self._async_relation_boundary_setup = False

    async def cleanup_after_test(self, scenario_name: str):
        for backend in self._active_async_backends:
            try:
                try:
                    if self._created_tables:
                        await backend.execute("SET FOREIGN_KEY_CHECKS = 0")
                        for table in list(self._created_tables):
                            try:
                                await backend.execute(f"DROP TABLE IF EXISTS `{table}`")
                            except Exception:
                                pass
                        await backend.execute("SET FOREIGN_KEY_CHECKS = 1")
                except Exception:
                    try:
                        await backend.execute("SET FOREIGN_KEY_CHECKS = 1")
                    except Exception:
                        pass
            finally:
                try:
                    await backend.disconnect()
                except Exception:
                    pass
        self._active_async_backends.clear()
        self._created_tables.clear()
        self._reset_async_setup_state()
