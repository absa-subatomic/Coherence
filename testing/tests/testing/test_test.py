import time
from unittest.mock import MagicMock

from subatomic_coherence.testing.test import TestPortal, ResultCode, TestResult, TestElement, CallStackAction
from subatomic_coherence.user.slack_user import SlackUser
from subatomic_coherence.user.slack_user_workspace import SlackUserWorkspace


def test_test_portal_test_simple_expect_success():
    test = TestPortal()
    result = test.test([])
    assert result.result_code == ResultCode.success
    assert result.result == "success"
    assert test.is_live is False


def test_test_portal_test_simple_expect_failure():
    test = TestPortal()
    test.run_element = lambda slack_user_workspace, data_store: TestResult(ResultCode.failure, "FAILURE")
    result = test.test([])
    assert result.result_code == ResultCode.failure
    assert result.result == "failure"
    assert result.message == "FAILURE"
    assert test.is_live is False


def test_test_portal_test_with_child_expect_failure():
    test = TestPortal().then(lambda slack_user_workspace, data_store: TestResult(ResultCode.failure, "FAILURE"))
    user_workspace = SlackUserWorkspace()
    result = test.test(user_workspace)
    assert result.result_code == ResultCode.pending
    assert test.is_live is True
    result = test.test(user_workspace)
    assert result.result_code == ResultCode.failure
    assert result.result == "failure"
    assert result.message == "FAILURE"
    assert test.is_live is False


def test_test_portal_test_timeout_expect_failure():
    test = TestPortal(timeout=10)
    test.run_element = lambda slack_user_workspace, data_store: TestResult(ResultCode.pending)
    user_workspace = SlackUserWorkspace()
    result = test.test(user_workspace)
    assert result.result_code == ResultCode.pending
    time.sleep(0.015)
    result = test.test(user_workspace)
    assert result.result_code == ResultCode.failure
    assert test.is_live is False
    assert result.message.startswith("Time out occurred when calling") is True


def test_test_portal_data_store_expect_data_persisted_between_steps():
    def mock_action1(slack_user_workspace, data_store):
        data_store["action1"] = "value1"
        return TestResult(ResultCode.success)

    def mock_action2(slack_user_workspace, data_store):
        data_store["action2"] = "value2"
        return TestResult(ResultCode.success)

    test = TestPortal()
    test.then(mock_action1).then(mock_action2)
    user_workspace = SlackUserWorkspace()
    # Run TestPortal initial run element
    test.test(user_workspace)
    # Run mock_action_1
    test.test(user_workspace)
    assert test.data_store["action1"] == "value1"
    # Run mock_action_2
    test.test(user_workspace)
    assert test.data_store["action1"] == "value1"
    assert test.data_store["action2"] == "value2"


def test_test_portal_failed_test_call_stack_expect_correct_call_stack():
    def mock_action1(slack_user_workspace, data_store):
        return TestResult(ResultCode.success)

    def mock_action2(slack_user_workspace, data_store):
        return TestResult(ResultCode.failure)

    test = TestPortal()
    test.then(mock_action1).then(mock_action2)
    test.name = "portal"
    user_workspace = SlackUserWorkspace()
    # Run TestPortal initial run element
    test.test(user_workspace)
    # Run mock_action_1
    test.test(user_workspace)
    # Run mock_action_2
    result = test.test(user_workspace)
    assert result.call_stack == "portal\n.then(mock_action1)\n.then(mock_action2)"


def test_test_portal_failed_test_with_processed_event_call_stack_expect_correct_call_stack():
    def mock_action1(slack_user_workspace, data_store):
        for event in slack_user_workspace.find_user_client_by_username().events:
            # marks event at 0 as processed
            break
        return TestResult(ResultCode.success)

    def mock_action2(slack_user_workspace, data_store):
        return TestResult(ResultCode.failure)

    user1 = SlackUser("user1", "token")
    user1.load_events({"id": "1"})

    test = TestPortal()
    test.then(mock_action1).then(mock_action2)
    test.name = "portal"
    user_workspace = SlackUserWorkspace()
    user_workspace.find_user_client_by_username = MagicMock(return_value=user1)
    user_workspace.add_slack_user_client(user1)
    # Run TestPortal initial run element
    test.test(user_workspace)
    # Run mock_action_1
    test.test(user_workspace)
    # Run mock_action_2
    result = test.test(user_workspace)
    assert result.call_stack == "portal\n.then(mock_action1) - {\"id\": \"1\"}\n.then(mock_action2)"


def test_test_portal_failed_test_with_runtime_error_expect_failed_test_result():
    def mock_action1(slack_user_workspace, data_store):
        message = ""[10]  # this will throw a runtime error
        return TestResult(ResultCode.success, message)

    test = TestPortal()
    test.then(mock_action1)
    test.name = "portal"
    # Run TestPortal initial run element
    test.test([])
    # Run mock_action_1
    result = test.test([])
    assert result.result_code == ResultCode.failure


def test_test_portal_build_simple_stack_message_expect_correct_stack_message():
    test = TestPortal()
    test.name = "portal"
    test.simple_call_stack += [CallStackAction("mock1")]
    test.simple_call_stack += [CallStackAction("mock2")]
    result = test._build_simple_stack_message()
    assert result == "portal\n.then(mock1)\n.then(mock2)"


def test_test_portal_push_action_onto_stack_expect_correct_function_name_pushed_onto_stack():
    def some_function():
        pass

    test = TestPortal().then(some_function)
    test._push_action_onto_stack(test.current_action.next_action)
    assert test.simple_call_stack[0].name == "some_function"


def test_test_portal_add_clean_up_function_expect_clean_up_function_created():
    def some_function(slack_user_workspace):
        pass

    test = TestPortal().set_clean_up(some_function)

    assert test.clean_up == some_function
