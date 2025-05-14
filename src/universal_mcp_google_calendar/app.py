from datetime import datetime, timedelta, timezone

from typing import Any
from loguru import logger

from universal_mcp.applications.application import APIApplication
from universal_mcp.integrations import Integration


class GoogleCalendarApp(APIApplication):
    def __init__(self, integration: Integration) -> None:
        super().__init__(name="google-calendar", integration=integration)
        self.base_api_url = "https://www.googleapis.com/calendar/v3/calendars/primary"
        self.base_url = "https://www.googleapis.com/calendar/v3"

    def _format_datetime(self, dt_string: str) -> str:
        """Format a datetime string from ISO format to a human-readable format.

        Args:
            dt_string: A datetime string in ISO format (e.g., "2023-06-01T10:00:00Z")

        Returns:
            A formatted datetime string (e.g., "2023-06-01 10:00 AM") or the original string with
            "(All day)" appended if it's just a date
        """
        if not dt_string or dt_string == "Unknown":
            return "Unknown"

        # Check if it's just a date (all-day event) or a datetime
        if "T" in dt_string:
            # It's a datetime - parse and format it
            try:
                # Handle Z (UTC) suffix by replacing with +00:00 timezone
                if dt_string.endswith("Z"):
                    dt_string = dt_string.replace("Z", "+00:00")

                # Parse the ISO datetime string
                dt = datetime.fromisoformat(dt_string)

                # Format to a more readable form
                return dt.strftime("%Y-%m-%d %I:%M %p")
            except ValueError:
                # In case of parsing error, return the original
                logger.warning(f"Could not parse datetime string: {dt_string}")
                return dt_string
        else:
            # It's just a date (all-day event)
            return f"{dt_string} (All day)"

    def get_today_events(
        self, days: int = 1, max_results: int = None, time_zone: str = None
    ) -> str:
        """
        Retrieves and formats events from Google Calendar for today or a specified number of future days, with optional result limiting and timezone specification.

        Args:
            days: Number of days to retrieve events for (default: 1, which is just today)
            max_results: Maximum number of events to return (optional)
            time_zone: Time zone used in the response (optional, default is calendar's time zone)

        Returns:
            A formatted string containing a list of calendar events with their times and IDs, or a message indicating no events were found

        Raises:
            HTTPError: Raised when the API request fails or returns an error status code

        Tags:
            fetch, list, calendar, events, date-time, important, api, formatting
        """
        today = datetime.now(timezone.utc).date()
        end_date = today + timedelta(days=days)
        time_min = f"{today.isoformat()}T00:00:00Z"
        time_max = f"{end_date.isoformat()}T00:00:00Z"
        url = f"{self.base_api_url}/events"
        params = {
            "timeMin": time_min,
            "timeMax": time_max,
            "singleEvents": "true",
            "orderBy": "startTime",
        }
        if max_results is not None:
            params["maxResults"] = max_results
        if time_zone:
            params["timeZone"] = time_zone
        date_range = "today" if days == 1 else f"the next {days} days"
        logger.info(f"Retrieving calendar events for {date_range}")
        response = self._get(url, params=params)
        response.raise_for_status()
        events = response.json().get("items", [])
        if not events:
            return f"No events scheduled for {date_range}."
        result = f"Events for {date_range}:\n\n"
        for event in events:
            # Extract event date and time
            start = event.get("start", {})
            event_date = (
                start.get("date", start.get("dateTime", "")).split("T")[0]
                if "T" in start.get("dateTime", "")
                else start.get("date", "")
            )

            # Extract and format time
            start_time = start.get("dateTime", start.get("date", "All day"))

            # Format the time display
            if "T" in start_time:  # It's a datetime
                formatted_time = self._format_datetime(start_time)
                # For multi-day view, keep the date; for single day, just show time
                if days > 1:
                    time_display = formatted_time
                else:
                    # Extract just the time part
                    time_display = (
                        formatted_time.split(" ")[1]
                        + " "
                        + formatted_time.split(" ")[2]
                    )
            else:  # It's an all-day event
                time_display = f"{event_date} (All day)" if days > 1 else "All day"

            # Get event details
            summary = event.get("summary", "Untitled event")
            event_id = event.get("id", "No ID")

            result += f"- {time_display}: {summary} (ID: {event_id})\n"
        return result

    def get_event(
        self, event_id: str, max_attendees: int = None, time_zone: str = None
    ) -> str:
        """
        Retrieves and formats detailed information about a specific Google Calendar event by its ID

        Args:
            event_id: The unique identifier of the calendar event to retrieve
            max_attendees: Optional. The maximum number of attendees to include in the response. If None, includes all attendees
            time_zone: Optional. The time zone to use for formatting dates in the response. If None, uses the calendar's default time zone

        Returns:
            A formatted string containing comprehensive event details including summary, time, location, description, creator, organizer, recurrence status, and attendee information

        Raises:
            HTTPError: Raised when the API request fails or returns an error status code
            JSONDecodeError: Raised when the API response cannot be parsed as JSON

        Tags:
            retrieve, calendar, event, format, api, important
        """
        url = f"{self.base_api_url}/events/{event_id}"
        params = {}
        if max_attendees is not None:
            params["maxAttendees"] = max_attendees
        if time_zone:
            params["timeZone"] = time_zone
        logger.info(f"Retrieving calendar event with ID: {event_id}")
        response = self._get(url, params=params)
        response.raise_for_status()
        event = response.json()
        summary = event.get("summary", "Untitled event")
        description = event.get("description", "No description")
        location = event.get("location", "No location specified")
        start = event.get("start", {})
        end = event.get("end", {})
        start_time = start.get("dateTime", start.get("date", "Unknown"))
        end_time = end.get("dateTime", end.get("date", "Unknown"))
        start_formatted = self._format_datetime(start_time)
        end_formatted = self._format_datetime(end_time)
        creator = event.get("creator", {}).get("email", "Unknown")
        organizer = event.get("organizer", {}).get("email", "Unknown")
        recurrence = "Yes" if "recurrence" in event else "No"
        attendees = event.get("attendees", [])
        attendee_info = ""
        if attendees:
            attendee_info = "\nAttendees:\n"
            for i, attendee in enumerate(attendees, 1):
                email = attendee.get("email", "No email")
                name = attendee.get("displayName", email)
                response_status = attendee.get("responseStatus", "Unknown")

                status_mapping = {
                    "accepted": "Accepted",
                    "declined": "Declined",
                    "tentative": "Maybe",
                    "needsAction": "Not responded",
                }

                formatted_status = status_mapping.get(response_status, response_status)
                attendee_info += f"  {i}. {name} ({email}) - {formatted_status}\n"
        result = f"Event: {summary}\n"
        result += f"ID: {event_id}\n"
        result += f"When: {start_formatted} to {end_formatted}\n"
        result += f"Where: {location}\n"
        result += f"Description: {description}\n"
        result += f"Creator: {creator}\n"
        result += f"Organizer: {organizer}\n"
        result += f"Recurring: {recurrence}\n"
        result += attendee_info
        return result

    def list_events(
        self,
        max_results: int = 10,
        time_min: str = None,
        time_max: str = None,
        q: str = None,
        order_by: str = "startTime",
        single_events: bool = True,
        time_zone: str = None,
        page_token: str = None,
    ) -> str:
        """
        Retrieves and formats a list of events from Google Calendar with customizable filtering, sorting, and pagination options

        Args:
            max_results: Maximum number of events to return (default: 10, max: 2500)
            time_min: Start time in ISO format (e.g., '2023-12-01T00:00:00Z'). Defaults to current time if not specified
            time_max: End time in ISO format (e.g., '2023-12-31T23:59:59Z')
            q: Free text search terms to filter events (searches across summary, description, location, attendees)
            order_by: Sort order for results - either 'startTime' (default) or 'updated'
            single_events: Whether to expand recurring events into individual instances (default: True)
            time_zone: Time zone for response formatting (defaults to calendar's time zone)
            page_token: Token for retrieving a specific page of results in paginated responses

        Returns:
            A formatted string containing the list of events with details including summary, ID, start time, and location, or a message if no events are found

        Raises:
            HTTPError: Raised when the API request fails or returns an error status code

        Tags:
            list, calendar, events, search, filter, pagination, format, important
        """
        url = f"{self.base_api_url}/events"
        params = {
            "maxResults": max_results,
            "singleEvents": str(single_events).lower(),
            "orderBy": order_by,
        }
        if time_min:
            params["timeMin"] = time_min
        else:
            # Default to current time if not specified
            now = datetime.utcnow().isoformat() + "Z"  # 'Z' indicates UTC time
            params["timeMin"] = now
        if time_max:
            params["timeMax"] = time_max
        if q:
            params["q"] = q
        if time_zone:
            params["timeZone"] = time_zone
        if page_token:
            params["pageToken"] = page_token
        logger.info(f"Retrieving calendar events with params: {params}")
        response = self._get(url, params=params)
        response.raise_for_status()
        data = response.json()
        events = data.get("items", [])
        if not events:
            return "No events found matching your criteria."
        calendar_summary = data.get("summary", "Your Calendar")
        time_zone_info = data.get("timeZone", "Unknown")
        result = f"Events from {calendar_summary} (Time Zone: {time_zone_info}):\n\n"
        for i, event in enumerate(events, 1):
            # Get basic event details
            event_id = event.get("id", "No ID")
            summary = event.get("summary", "Untitled event")

            # Get event times and format them
            start = event.get("start", {})
            start_time = start.get("dateTime", start.get("date", "Unknown"))

            # Format the start time using the helper function
            start_formatted = self._format_datetime(start_time)

            # Get location if available
            location = event.get("location", "No location specified")

            # Check if it's a recurring event
            is_recurring = "recurrence" in event
            recurring_info = " (Recurring)" if is_recurring else ""

            # Format the event information
            result += f"{i}. {summary}{recurring_info}\n"
            result += f"   ID: {event_id}\n"
            result += f"   When: {start_formatted}\n"
            result += f"   Where: {location}\n"

            # Add a separator between events
            if i < len(events):
                result += "\n"
        if "nextPageToken" in data:
            next_token = data.get("nextPageToken")
            result += (
                f"\nMore events available. Use page_token='{next_token}' to see more."
            )
        return result

    def quick_add_event(self, text: str, send_updates: str = "none") -> str:
        """
        Creates a calendar event using natural language text input and returns a formatted confirmation message with event details.

        Args:
            text: Natural language text describing the event (e.g., 'Meeting with John at Coffee Shop tomorrow 3pm-4pm')
            send_updates: Specifies who should receive event notifications: 'all', 'externalOnly', or 'none' (default)

        Returns:
            A formatted string containing the confirmation message with event details including summary, time, location, and event ID

        Raises:
            HTTPError: Raised when the API request fails or returns an error status code

        Tags:
            create, calendar, event, quick-add, natural-language, important
        """
        url = f"{self.base_api_url}/events/quickAdd"
        params = {"text": text, "sendUpdates": send_updates}
        logger.info(f"Creating event via quickAdd: '{text}'")
        response = self._post(url, data=None, params=params)
        response.raise_for_status()
        event = response.json()
        event_id = event.get("id", "Unknown")
        summary = event.get("summary", "Untitled event")
        start = event.get("start", {})
        end = event.get("end", {})
        start_time = start.get("dateTime", start.get("date", "Unknown"))
        end_time = end.get("dateTime", end.get("date", "Unknown"))
        start_formatted = self._format_datetime(start_time)
        end_formatted = self._format_datetime(end_time)
        location = event.get("location", "No location specified")
        result = "Successfully created event!\n\n"
        result += f"Summary: {summary}\n"
        result += f"When: {start_formatted}"
        if start_formatted != end_formatted:
            result += f" to {end_formatted}"
        result += f"\nWhere: {location}\n"
        result += f"Event ID: {event_id}\n"
        result += f"\nUse get_event('{event_id}') to see full details."
        return result

    def get_event_instances(
        self,
        event_id: str,
        max_results: int = 25,
        time_min: str = None,
        time_max: str = None,
        time_zone: str = None,
        show_deleted: bool = False,
        page_token: str = None,
    ) -> str:
        """
        Retrieves and formats all instances of a recurring calendar event within a specified time range, showing details like time, status, and modifications for each occurrence.

        Args:
            event_id: ID of the recurring event
            max_results: Maximum number of event instances to return (default: 25, max: 2500)
            time_min: Lower bound (inclusive) for event's end time in ISO format
            time_max: Upper bound (exclusive) for event's start time in ISO format
            time_zone: Time zone used in the response (defaults to calendar's time zone)
            show_deleted: Whether to include deleted instances (default: False)
            page_token: Token for retrieving a specific page of results

        Returns:
            A formatted string containing a list of event instances with details including time, status, instance ID, and modification information, plus pagination token if applicable.

        Raises:
            HTTPError: Raised when the API request fails or returns an error status code
            JSONDecodeError: Raised when the API response cannot be parsed as JSON

        Tags:
            list, retrieve, calendar, events, recurring, pagination, formatting, important
        """
        url = f"{self.base_api_url}/events/{event_id}/instances"
        params = {"maxResults": max_results, "showDeleted": str(show_deleted).lower()}
        if time_min:
            params["timeMin"] = time_min
        if time_max:
            params["timeMax"] = time_max
        if time_zone:
            params["timeZone"] = time_zone
        if page_token:
            params["pageToken"] = page_token
        logger.info(f"Retrieving instances of recurring event with ID: {event_id}")
        response = self._get(url, params=params)
        response.raise_for_status()
        data = response.json()
        instances = data.get("items", [])
        if not instances:
            return f"No instances found for recurring event with ID: {event_id}"
        parent_summary = instances[0].get("summary", "Untitled recurring event")
        result = f"Instances of recurring event: {parent_summary}\n\n"
        for i, instance in enumerate(instances, 1):
            # Get instance ID and status
            instance_id = instance.get("id", "No ID")
            status = instance.get("status", "confirmed")

            # Format status for display
            status_display = ""
            if status == "cancelled":
                status_display = " [CANCELLED]"
            elif status == "tentative":
                status_display = " [TENTATIVE]"

            # Get instance time
            start = instance.get("start", {})
            original_start_time = instance.get("originalStartTime", {})

            # Determine if this is a modified instance
            is_modified = original_start_time and "dateTime" in original_start_time
            modified_indicator = " [MODIFIED]" if is_modified else ""

            # Get the time information
            start_time = start.get("dateTime", start.get("date", "Unknown"))

            # Format the time using the helper function
            formatted_time = self._format_datetime(start_time)

            # Format the instance information
            result += f"{i}. {formatted_time}{status_display}{modified_indicator}\n"
            result += f"   Instance ID: {instance_id}\n"

            # Show original start time if modified
            if is_modified:
                orig_time = original_start_time.get(
                    "dateTime", original_start_time.get("date", "Unknown")
                )
                orig_formatted = self._format_datetime(orig_time)
                result += f"   Original time: {orig_formatted}\n"

            # Add a separator between instances
            if i < len(instances):
                result += "\n"
        if "nextPageToken" in data:
            next_token = data.get("nextPageToken")
            result += f"\nMore instances available. Use page_token='{next_token}' to see more."
        return result

    def get_access_control_rule(self, calendarId, ruleId, alt=None, fields=None, key=None, oauth_token=None, prettyPrint=None, quotaUser=None, userIp=None) -> dict[str, Any]:
        """
        Get Access Control Rule

        Args:
            calendarId (string): calendarId
            ruleId (string): ruleId
            alt (string): Data format for the response. Example: 'json'.
            fields (string): Selector specifying which fields to include in a partial response. Example: 'amet in'.
            key (string): API key. Your API key identifies your project and provides you with API access, quota, and reports. Required unless you provide an OAuth 2.0 token. Example: 'amet in'.
            oauth_token (string): OAuth 2.0 token for the current user. Example: 'amet in'.
            prettyPrint (string): Returns response with indentations and line breaks. Example: 'true'.
            quotaUser (string): An opaque string that represents a user for quota purposes. Must not exceed 40 characters. Example: 'amet in'.
            userIp (string): Deprecated. Please use quotaUser instead. Example: 'amet in'.

        Returns:
            dict[str, Any]: Successful response

        Tags:
            calendars, {calendarId}, acl, {ruleId}
        """
        if calendarId is None:
            raise ValueError("Missing required parameter 'calendarId'")
        if ruleId is None:
            raise ValueError("Missing required parameter 'ruleId'")
        url = f"{self.base_url}/calendars/{calendarId}/acl/{ruleId}"
        query_params = {k: v for k, v in [('alt', alt), ('fields', fields), ('key', key), ('oauth_token', oauth_token), ('prettyPrint', prettyPrint), ('quotaUser', quotaUser), ('userIp', userIp)] if v is not None}
        response = self._get(url, params=query_params)
        response.raise_for_status()
        return response.json()

    def update_access_control_rule(self, calendarId, ruleId, sendNotifications=None, alt=None, fields=None, key=None, oauth_token=None, prettyPrint=None, quotaUser=None, userIp=None, etag=None, id=None, kind=None, role=None, scope=None) -> dict[str, Any]:
        """
        Update Access Control Rule

        Args:
            calendarId (string): calendarId
            ruleId (string): ruleId
            sendNotifications (string): No description provided. Example: 'true'.
            alt (string): Data format for the response. Example: 'json'.
            fields (string): Selector specifying which fields to include in a partial response. Example: 'amet in'.
            key (string): API key. Your API key identifies your project and provides you with API access, quota, and reports. Required unless you provide an OAuth 2.0 token. Example: 'amet in'.
            oauth_token (string): OAuth 2.0 token for the current user. Example: 'amet in'.
            prettyPrint (string): Returns response with indentations and line breaks. Example: 'true'.
            quotaUser (string): An opaque string that represents a user for quota purposes. Must not exceed 40 characters. Example: 'amet in'.
            userIp (string): Deprecated. Please use quotaUser instead. Example: 'amet in'.
            etag (string): etag Example: 'velit eu voluptate'.
            id (string): id Example: 'ex dolore in sint'.
            kind (string): kind Example: 'calendar#aclRule'.
            role (string): role Example: 'et'.
            scope (object): scope
                Example:
                ```json
                {
                  "etag": "velit eu voluptate",
                  "id": "ex dolore in sint",
                  "kind": "calendar#aclRule",
                  "role": "et",
                  "scope": {
                    "type": "sit eiusmod culpa do",
                    "value": "quis esse"
                  }
                }
                ```

        Returns:
            dict[str, Any]: Successful response

        Tags:
            calendars, {calendarId}, acl, {ruleId}
        """
        if calendarId is None:
            raise ValueError("Missing required parameter 'calendarId'")
        if ruleId is None:
            raise ValueError("Missing required parameter 'ruleId'")
        request_body = {
            'etag': etag,
            'id': id,
            'kind': kind,
            'role': role,
            'scope': scope,
        }
        request_body = {k: v for k, v in request_body.items() if v is not None}
        url = f"{self.base_url}/calendars/{calendarId}/acl/{ruleId}"
        query_params = {k: v for k, v in [('sendNotifications', sendNotifications), ('alt', alt), ('fields', fields), ('key', key), ('oauth_token', oauth_token), ('prettyPrint', prettyPrint), ('quotaUser', quotaUser), ('userIp', userIp)] if v is not None}
        response = self._put(url, data=request_body, params=query_params)
        response.raise_for_status()
        return response.json()

    def delete_access_control_rule(self, calendarId, ruleId, alt=None, fields=None, key=None, oauth_token=None, prettyPrint=None, quotaUser=None, userIp=None) -> Any:
        """
        Delete Access Control Rule

        Args:
            calendarId (string): calendarId
            ruleId (string): ruleId
            alt (string): Data format for the response. Example: 'json'.
            fields (string): Selector specifying which fields to include in a partial response. Example: 'amet in'.
            key (string): API key. Your API key identifies your project and provides you with API access, quota, and reports. Required unless you provide an OAuth 2.0 token. Example: 'amet in'.
            oauth_token (string): OAuth 2.0 token for the current user. Example: 'amet in'.
            prettyPrint (string): Returns response with indentations and line breaks. Example: 'true'.
            quotaUser (string): An opaque string that represents a user for quota purposes. Must not exceed 40 characters. Example: 'amet in'.
            userIp (string): Deprecated. Please use quotaUser instead. Example: 'amet in'.

        Returns:
            Any: No Content

        Tags:
            calendars, {calendarId}, acl, {ruleId}
        """
        if calendarId is None:
            raise ValueError("Missing required parameter 'calendarId'")
        if ruleId is None:
            raise ValueError("Missing required parameter 'ruleId'")
        url = f"{self.base_url}/calendars/{calendarId}/acl/{ruleId}"
        query_params = {k: v for k, v in [('alt', alt), ('fields', fields), ('key', key), ('oauth_token', oauth_token), ('prettyPrint', prettyPrint), ('quotaUser', quotaUser), ('userIp', userIp)] if v is not None}
        response = self._delete(url, params=query_params)
        response.raise_for_status()
        return response.json()

    def patch_access_control_rule(self, calendarId, ruleId, sendNotifications=None, alt=None, fields=None, key=None, oauth_token=None, prettyPrint=None, quotaUser=None, userIp=None, etag=None, id=None, kind=None, role=None, scope=None) -> dict[str, Any]:
        """
        Patch Access Control Rule

        Args:
            calendarId (string): calendarId
            ruleId (string): ruleId
            sendNotifications (string): No description provided. Example: 'true'.
            alt (string): Data format for the response. Example: 'json'.
            fields (string): Selector specifying which fields to include in a partial response. Example: 'amet in'.
            key (string): API key. Your API key identifies your project and provides you with API access, quota, and reports. Required unless you provide an OAuth 2.0 token. Example: 'amet in'.
            oauth_token (string): OAuth 2.0 token for the current user. Example: 'amet in'.
            prettyPrint (string): Returns response with indentations and line breaks. Example: 'true'.
            quotaUser (string): An opaque string that represents a user for quota purposes. Must not exceed 40 characters. Example: 'amet in'.
            userIp (string): Deprecated. Please use quotaUser instead. Example: 'amet in'.
            etag (string): etag Example: 'velit eu voluptate'.
            id (string): id Example: 'ex dolore in sint'.
            kind (string): kind Example: 'calendar#aclRule'.
            role (string): role Example: 'et'.
            scope (object): scope
                Example:
                ```json
                {
                  "etag": "velit eu voluptate",
                  "id": "ex dolore in sint",
                  "kind": "calendar#aclRule",
                  "role": "et",
                  "scope": {
                    "type": "sit eiusmod culpa do",
                    "value": "quis esse"
                  }
                }
                ```

        Returns:
            dict[str, Any]: Successful response

        Tags:
            calendars, {calendarId}, acl, {ruleId}
        """
        if calendarId is None:
            raise ValueError("Missing required parameter 'calendarId'")
        if ruleId is None:
            raise ValueError("Missing required parameter 'ruleId'")
        request_body = {
            'etag': etag,
            'id': id,
            'kind': kind,
            'role': role,
            'scope': scope,
        }
        request_body = {k: v for k, v in request_body.items() if v is not None}
        url = f"{self.base_url}/calendars/{calendarId}/acl/{ruleId}"
        query_params = {k: v for k, v in [('sendNotifications', sendNotifications), ('alt', alt), ('fields', fields), ('key', key), ('oauth_token', oauth_token), ('prettyPrint', prettyPrint), ('quotaUser', quotaUser), ('userIp', userIp)] if v is not None}
        response = self._patch(url, data=request_body, params=query_params)
        response.raise_for_status()
        return response.json()

    def return_access_control_rules(self, calendarId, maxResults=None, pageToken=None, showDeleted=None, syncToken=None, alt=None, fields=None, key=None, oauth_token=None, prettyPrint=None, quotaUser=None, userIp=None) -> dict[str, Any]:
        """
        Return Access Control Rules

        Args:
            calendarId (string): calendarId
            maxResults (string): No description provided. Example: '54806309'.
            pageToken (string): No description provided. Example: 'amet in'.
            showDeleted (string): No description provided. Example: 'true'.
            syncToken (string): No description provided. Example: 'amet in'.
            alt (string): Data format for the response. Example: 'json'.
            fields (string): Selector specifying which fields to include in a partial response. Example: 'amet in'.
            key (string): API key. Your API key identifies your project and provides you with API access, quota, and reports. Required unless you provide an OAuth 2.0 token. Example: 'amet in'.
            oauth_token (string): OAuth 2.0 token for the current user. Example: 'amet in'.
            prettyPrint (string): Returns response with indentations and line breaks. Example: 'true'.
            quotaUser (string): An opaque string that represents a user for quota purposes. Must not exceed 40 characters. Example: 'amet in'.
            userIp (string): Deprecated. Please use quotaUser instead. Example: 'amet in'.

        Returns:
            dict[str, Any]: Successful response

        Tags:
            calendars, {calendarId}, acl
        """
        if calendarId is None:
            raise ValueError("Missing required parameter 'calendarId'")
        url = f"{self.base_url}/calendars/{calendarId}/acl"
        query_params = {k: v for k, v in [('maxResults', maxResults), ('pageToken', pageToken), ('showDeleted', showDeleted), ('syncToken', syncToken), ('alt', alt), ('fields', fields), ('key', key), ('oauth_token', oauth_token), ('prettyPrint', prettyPrint), ('quotaUser', quotaUser), ('userIp', userIp)] if v is not None}
        response = self._get(url, params=query_params)
        response.raise_for_status()
        return response.json()

    def insert_access_control_rule(self, calendarId, sendNotifications=None, alt=None, fields=None, key=None, oauth_token=None, prettyPrint=None, quotaUser=None, userIp=None, etag=None, id=None, kind=None, role=None, scope=None) -> dict[str, Any]:
        """
        Insert Access Control Rule

        Args:
            calendarId (string): calendarId
            sendNotifications (string): No description provided. Example: 'true'.
            alt (string): Data format for the response. Example: 'json'.
            fields (string): Selector specifying which fields to include in a partial response. Example: 'amet in'.
            key (string): API key. Your API key identifies your project and provides you with API access, quota, and reports. Required unless you provide an OAuth 2.0 token. Example: 'amet in'.
            oauth_token (string): OAuth 2.0 token for the current user. Example: 'amet in'.
            prettyPrint (string): Returns response with indentations and line breaks. Example: 'true'.
            quotaUser (string): An opaque string that represents a user for quota purposes. Must not exceed 40 characters. Example: 'amet in'.
            userIp (string): Deprecated. Please use quotaUser instead. Example: 'amet in'.
            etag (string): etag Example: 'velit eu voluptate'.
            id (string): id Example: 'ex dolore in sint'.
            kind (string): kind Example: 'calendar#aclRule'.
            role (string): role Example: 'et'.
            scope (object): scope
                Example:
                ```json
                {
                  "etag": "velit eu voluptate",
                  "id": "ex dolore in sint",
                  "kind": "calendar#aclRule",
                  "role": "et",
                  "scope": {
                    "type": "sit eiusmod culpa do",
                    "value": "quis esse"
                  }
                }
                ```

        Returns:
            dict[str, Any]: Successful response

        Tags:
            calendars, {calendarId}, acl
        """
        if calendarId is None:
            raise ValueError("Missing required parameter 'calendarId'")
        request_body = {
            'etag': etag,
            'id': id,
            'kind': kind,
            'role': role,
            'scope': scope,
        }
        request_body = {k: v for k, v in request_body.items() if v is not None}
        url = f"{self.base_url}/calendars/{calendarId}/acl"
        query_params = {k: v for k, v in [('sendNotifications', sendNotifications), ('alt', alt), ('fields', fields), ('key', key), ('oauth_token', oauth_token), ('prettyPrint', prettyPrint), ('quotaUser', quotaUser), ('userIp', userIp)] if v is not None}
        response = self._post(url, data=request_body, params=query_params)
        response.raise_for_status()
        return response.json()

    def watch_access_control_rules(self, calendarId, maxResults=None, pageToken=None, showDeleted=None, syncToken=None, alt=None, fields=None, key=None, oauth_token=None, prettyPrint=None, quotaUser=None, userIp=None, address=None, expiration=None, id=None, kind=None, params=None, payload=None, resourceId=None, resourceUri=None, token=None, type=None) -> dict[str, Any]:
        """
        Watch Access Control Rules

        Args:
            calendarId (string): calendarId
            maxResults (string): No description provided. Example: '54806309'.
            pageToken (string): No description provided. Example: 'amet in'.
            showDeleted (string): No description provided. Example: 'true'.
            syncToken (string): No description provided. Example: 'amet in'.
            alt (string): Data format for the response. Example: 'json'.
            fields (string): Selector specifying which fields to include in a partial response. Example: 'amet in'.
            key (string): API key. Your API key identifies your project and provides you with API access, quota, and reports. Required unless you provide an OAuth 2.0 token. Example: 'amet in'.
            oauth_token (string): OAuth 2.0 token for the current user. Example: 'amet in'.
            prettyPrint (string): Returns response with indentations and line breaks. Example: 'true'.
            quotaUser (string): An opaque string that represents a user for quota purposes. Must not exceed 40 characters. Example: 'amet in'.
            userIp (string): Deprecated. Please use quotaUser instead. Example: 'amet in'.
            address (string): address Example: 'incididunt sed consequat'.
            expiration (string): expiration Example: 'velit ad aliq'.
            id (string): id Example: 'velit eiusmod'.
            kind (string): kind Example: 'api#channel'.
            params (object): params
            payload (boolean): payload Example: 'False'.
            resourceId (string): resourceId Example: 'aute'.
            resourceUri (string): resourceUri Example: 'fugiat consequat'.
            token (string): token Example: 'ullamco officia in'.
            type (string): type
                Example:
                ```json
                {
                  "address": "incididunt sed consequat",
                  "expiration": "velit ad aliq",
                  "id": "velit eiusmod",
                  "kind": "api#channel",
                  "params": {
                    "reprehenderit5c": "non",
                    "sint_b": "cupidatat do"
                  },
                  "payload": false,
                  "resourceId": "aute",
                  "resourceUri": "fugiat consequat",
                  "token": "ullamco officia in",
                  "type": "ex eiusmod adipisicing mollit"
                }
                ```

        Returns:
            dict[str, Any]: Successful response

        Tags:
            calendars, {calendarId}, acl
        """
        if calendarId is None:
            raise ValueError("Missing required parameter 'calendarId'")
        request_body = {
            'address': address,
            'expiration': expiration,
            'id': id,
            'kind': kind,
            'params': params,
            'payload': payload,
            'resourceId': resourceId,
            'resourceUri': resourceUri,
            'token': token,
            'type': type,
        }
        request_body = {k: v for k, v in request_body.items() if v is not None}
        url = f"{self.base_url}/calendars/{calendarId}/acl/watch"
        query_params = {k: v for k, v in [('maxResults', maxResults), ('pageToken', pageToken), ('showDeleted', showDeleted), ('syncToken', syncToken), ('alt', alt), ('fields', fields), ('key', key), ('oauth_token', oauth_token), ('prettyPrint', prettyPrint), ('quotaUser', quotaUser), ('userIp', userIp)] if v is not None}
        response = self._post(url, data=request_body, params=query_params)
        response.raise_for_status()
        return response.json()

    def delete_event(self, calendarId, eventId, sendNotifications=None, sendUpdates=None, alt=None, fields=None, key=None, oauth_token=None, prettyPrint=None, quotaUser=None, userIp=None) -> Any:
        """
        Delete Event

        Args:
            calendarId (string): calendarId
            eventId (string): eventId
            sendNotifications (string): No description provided. Example: 'true'.
            sendUpdates (string): No description provided. Example: 'amet in'.
            alt (string): Data format for the response. Example: 'json'.
            fields (string): Selector specifying which fields to include in a partial response. Example: 'amet in'.
            key (string): API key. Your API key identifies your project and provides you with API access, quota, and reports. Required unless you provide an OAuth 2.0 token. Example: 'amet in'.
            oauth_token (string): OAuth 2.0 token for the current user. Example: 'amet in'.
            prettyPrint (string): Returns response with indentations and line breaks. Example: 'true'.
            quotaUser (string): An opaque string that represents a user for quota purposes. Must not exceed 40 characters. Example: 'amet in'.
            userIp (string): Deprecated. Please use quotaUser instead. Example: 'amet in'.

        Returns:
            Any: No Content

        Tags:
            calendars, {calendarId}, events, {eventId}
        """
        if calendarId is None:
            raise ValueError("Missing required parameter 'calendarId'")
        if eventId is None:
            raise ValueError("Missing required parameter 'eventId'")
        url = f"{self.base_url}/calendars/{calendarId}/events/{eventId}"
        query_params = {k: v for k, v in [('sendNotifications', sendNotifications), ('sendUpdates', sendUpdates), ('alt', alt), ('fields', fields), ('key', key), ('oauth_token', oauth_token), ('prettyPrint', prettyPrint), ('quotaUser', quotaUser), ('userIp', userIp)] if v is not None}
        response = self._delete(url, params=query_params)
        response.raise_for_status()
        return response.json()

    def insert_event(self, calendarId, eventId, alwaysIncludeEmail=None, maxAttendees=None, maxResults=None, originalStart=None, pageToken=None, showDeleted=None, timeMax=None, timeMin=None, timeZone=None, alt=None, fields=None, key=None, oauth_token=None, prettyPrint=None, quotaUser=None, userIp=None) -> Any:
        """
        Insert Event

        Args:
            calendarId (string): calendarId
            eventId (string): eventId
            alwaysIncludeEmail (string): No description provided. Example: 'true'.
            maxAttendees (string): No description provided. Example: '54806309'.
            maxResults (string): No description provided. Example: '54806309'.
            originalStart (string): No description provided. Example: 'amet in'.
            pageToken (string): No description provided. Example: 'amet in'.
            showDeleted (string): No description provided. Example: 'true'.
            timeMax (string): No description provided. Example: 'amet in'.
            timeMin (string): No description provided. Example: 'amet in'.
            timeZone (string): No description provided. Example: 'amet in'.
            alt (string): Data format for the response. Example: 'json'.
            fields (string): Selector specifying which fields to include in a partial response. Example: 'amet in'.
            key (string): API key. Your API key identifies your project and provides you with API access, quota, and reports. Required unless you provide an OAuth 2.0 token. Example: 'amet in'.
            oauth_token (string): OAuth 2.0 token for the current user. Example: 'amet in'.
            prettyPrint (string): Returns response with indentations and line breaks. Example: 'true'.
            quotaUser (string): An opaque string that represents a user for quota purposes. Must not exceed 40 characters. Example: 'amet in'.
            userIp (string): Deprecated. Please use quotaUser instead. Example: 'amet in'.

        Returns:
            Any: Successful response

        Tags:
            calendars, {calendarId}, events, {eventId}
        """
        if calendarId is None:
            raise ValueError("Missing required parameter 'calendarId'")
        if eventId is None:
            raise ValueError("Missing required parameter 'eventId'")
        url = f"{self.base_url}/calendars/{calendarId}/events/{eventId}/instances"
        query_params = {k: v for k, v in [('alwaysIncludeEmail', alwaysIncludeEmail), ('maxAttendees', maxAttendees), ('maxResults', maxResults), ('originalStart', originalStart), ('pageToken', pageToken), ('showDeleted', showDeleted), ('timeMax', timeMax), ('timeMin', timeMin), ('timeZone', timeZone), ('alt', alt), ('fields', fields), ('key', key), ('oauth_token', oauth_token), ('prettyPrint', prettyPrint), ('quotaUser', quotaUser), ('userIp', userIp)] if v is not None}
        response = self._get(url, params=query_params)
        response.raise_for_status()
        return response.json()

    def move_event(self, calendarId, eventId, destination=None, sendNotifications=None, sendUpdates=None, alt=None, fields=None, key=None, oauth_token=None, prettyPrint=None, quotaUser=None, userIp=None) -> Any:
        """
        Move Event

        Args:
            calendarId (string): calendarId
            eventId (string): eventId
            destination (string): (Required)  Example: 'amet in'.
            sendNotifications (string): No description provided. Example: 'true'.
            sendUpdates (string): No description provided. Example: 'amet in'.
            alt (string): Data format for the response. Example: 'json'.
            fields (string): Selector specifying which fields to include in a partial response. Example: 'amet in'.
            key (string): API key. Your API key identifies your project and provides you with API access, quota, and reports. Required unless you provide an OAuth 2.0 token. Example: 'amet in'.
            oauth_token (string): OAuth 2.0 token for the current user. Example: 'amet in'.
            prettyPrint (string): Returns response with indentations and line breaks. Example: 'true'.
            quotaUser (string): An opaque string that represents a user for quota purposes. Must not exceed 40 characters. Example: 'amet in'.
            userIp (string): Deprecated. Please use quotaUser instead. Example: 'amet in'.

        Returns:
            Any: Successful response

        Tags:
            calendars, {calendarId}, events, {eventId}
        """
        if calendarId is None:
            raise ValueError("Missing required parameter 'calendarId'")
        if eventId is None:
            raise ValueError("Missing required parameter 'eventId'")
        url = f"{self.base_url}/calendars/{calendarId}/events/{eventId}/move"
        query_params = {k: v for k, v in [('destination', destination), ('sendNotifications', sendNotifications), ('sendUpdates', sendUpdates), ('alt', alt), ('fields', fields), ('key', key), ('oauth_token', oauth_token), ('prettyPrint', prettyPrint), ('quotaUser', quotaUser), ('userIp', userIp)] if v is not None}
        response = self._post(url, data={}, params=query_params)
        response.raise_for_status()
        return response.json()

    def return_events_from_calendar(self, calendarId, alwaysIncludeEmail=None, eventTypes=None, iCalUID=None, maxAttendees=None, maxResults=None, orderBy=None, pageToken=None, privateExtendedProperty=None, q=None, sharedExtendedProperty=None, showDeleted=None, showHiddenInvitations=None, singleEvents=None, syncToken=None, timeMax=None, timeMin=None, timeZone=None, updatedMin=None, alt=None, fields=None, key=None, oauth_token=None, prettyPrint=None, quotaUser=None, userIp=None) -> Any:
        """
        Return Events from Calendar

        Args:
            calendarId (string): calendarId
            alwaysIncludeEmail (string): No description provided. Example: 'true'.
            eventTypes (string): No description provided. Example: 'amet in'.
            iCalUID (string): No description provided. Example: 'amet in'.
            maxAttendees (string): No description provided. Example: '54806309'.
            maxResults (string): No description provided. Example: '54806309'.
            orderBy (string): No description provided. Example: 'amet in'.
            pageToken (string): No description provided. Example: 'amet in'.
            privateExtendedProperty (string): No description provided. Example: 'amet in'.
            q (string): No description provided. Example: 'amet in'.
            sharedExtendedProperty (string): No description provided. Example: 'amet in'.
            showDeleted (string): No description provided. Example: 'true'.
            showHiddenInvitations (string): No description provided. Example: 'true'.
            singleEvents (string): No description provided. Example: 'true'.
            syncToken (string): No description provided. Example: 'amet in'.
            timeMax (string): No description provided. Example: 'amet in'.
            timeMin (string): No description provided. Example: 'amet in'.
            timeZone (string): No description provided. Example: 'amet in'.
            updatedMin (string): No description provided. Example: 'amet in'.
            alt (string): Data format for the response. Example: 'json'.
            fields (string): Selector specifying which fields to include in a partial response. Example: 'amet in'.
            key (string): API key. Your API key identifies your project and provides you with API access, quota, and reports. Required unless you provide an OAuth 2.0 token. Example: 'amet in'.
            oauth_token (string): OAuth 2.0 token for the current user. Example: 'amet in'.
            prettyPrint (string): Returns response with indentations and line breaks. Example: 'true'.
            quotaUser (string): An opaque string that represents a user for quota purposes. Must not exceed 40 characters. Example: 'amet in'.
            userIp (string): Deprecated. Please use quotaUser instead. Example: 'amet in'.

        Returns:
            Any: Successful response

        Tags:
            calendars, {calendarId}, events
        """
        if calendarId is None:
            raise ValueError("Missing required parameter 'calendarId'")
        url = f"{self.base_url}/calendars/{calendarId}/events"
        query_params = {k: v for k, v in [('alwaysIncludeEmail', alwaysIncludeEmail), ('eventTypes', eventTypes), ('iCalUID', iCalUID), ('maxAttendees', maxAttendees), ('maxResults', maxResults), ('orderBy', orderBy), ('pageToken', pageToken), ('privateExtendedProperty', privateExtendedProperty), ('q', q), ('sharedExtendedProperty', sharedExtendedProperty), ('showDeleted', showDeleted), ('showHiddenInvitations', showHiddenInvitations), ('singleEvents', singleEvents), ('syncToken', syncToken), ('timeMax', timeMax), ('timeMin', timeMin), ('timeZone', timeZone), ('updatedMin', updatedMin), ('alt', alt), ('fields', fields), ('key', key), ('oauth_token', oauth_token), ('prettyPrint', prettyPrint), ('quotaUser', quotaUser), ('userIp', userIp)] if v is not None}
        response = self._get(url, params=query_params)
        response.raise_for_status()
        return response.json()

    def watch_events(self, calendarId, alwaysIncludeEmail=None, eventTypes=None, iCalUID=None, maxAttendees=None, maxResults=None, orderBy=None, pageToken=None, privateExtendedProperty=None, q=None, sharedExtendedProperty=None, showDeleted=None, showHiddenInvitations=None, singleEvents=None, syncToken=None, timeMax=None, timeMin=None, timeZone=None, updatedMin=None, alt=None, fields=None, key=None, oauth_token=None, prettyPrint=None, quotaUser=None, userIp=None, address=None, expiration=None, id=None, kind=None, params=None, payload=None, resourceId=None, resourceUri=None, token=None, type=None) -> dict[str, Any]:
        """
        Watch Events

        Args:
            calendarId (string): calendarId
            alwaysIncludeEmail (string): No description provided. Example: 'true'.
            eventTypes (string): No description provided. Example: 'amet in'.
            iCalUID (string): No description provided. Example: 'amet in'.
            maxAttendees (string): No description provided. Example: '54806309'.
            maxResults (string): No description provided. Example: '54806309'.
            orderBy (string): No description provided. Example: 'amet in'.
            pageToken (string): No description provided. Example: 'amet in'.
            privateExtendedProperty (string): No description provided. Example: 'amet in'.
            q (string): No description provided. Example: 'amet in'.
            sharedExtendedProperty (string): No description provided. Example: 'amet in'.
            showDeleted (string): No description provided. Example: 'true'.
            showHiddenInvitations (string): No description provided. Example: 'true'.
            singleEvents (string): No description provided. Example: 'true'.
            syncToken (string): No description provided. Example: 'amet in'.
            timeMax (string): No description provided. Example: 'amet in'.
            timeMin (string): No description provided. Example: 'amet in'.
            timeZone (string): No description provided. Example: 'amet in'.
            updatedMin (string): No description provided. Example: 'amet in'.
            alt (string): Data format for the response. Example: 'json'.
            fields (string): Selector specifying which fields to include in a partial response. Example: 'amet in'.
            key (string): API key. Your API key identifies your project and provides you with API access, quota, and reports. Required unless you provide an OAuth 2.0 token. Example: 'amet in'.
            oauth_token (string): OAuth 2.0 token for the current user. Example: 'amet in'.
            prettyPrint (string): Returns response with indentations and line breaks. Example: 'true'.
            quotaUser (string): An opaque string that represents a user for quota purposes. Must not exceed 40 characters. Example: 'amet in'.
            userIp (string): Deprecated. Please use quotaUser instead. Example: 'amet in'.
            address (string): address Example: 'incididunt sed consequat'.
            expiration (string): expiration Example: 'velit ad aliq'.
            id (string): id Example: 'velit eiusmod'.
            kind (string): kind Example: 'api#channel'.
            params (object): params
            payload (boolean): payload Example: 'False'.
            resourceId (string): resourceId Example: 'aute'.
            resourceUri (string): resourceUri Example: 'fugiat consequat'.
            token (string): token Example: 'ullamco officia in'.
            type (string): type
                Example:
                ```json
                {
                  "address": "incididunt sed consequat",
                  "expiration": "velit ad aliq",
                  "id": "velit eiusmod",
                  "kind": "api#channel",
                  "params": {
                    "reprehenderit5c": "non",
                    "sint_b": "cupidatat do"
                  },
                  "payload": false,
                  "resourceId": "aute",
                  "resourceUri": "fugiat consequat",
                  "token": "ullamco officia in",
                  "type": "ex eiusmod adipisicing mollit"
                }
                ```

        Returns:
            dict[str, Any]: Successful response

        Tags:
            calendars, {calendarId}, events
        """
        if calendarId is None:
            raise ValueError("Missing required parameter 'calendarId'")
        request_body = {
            'address': address,
            'expiration': expiration,
            'id': id,
            'kind': kind,
            'params': params,
            'payload': payload,
            'resourceId': resourceId,
            'resourceUri': resourceUri,
            'token': token,
            'type': type,
        }
        request_body = {k: v for k, v in request_body.items() if v is not None}
        url = f"{self.base_url}/calendars/{calendarId}/events/watch"
        query_params = {k: v for k, v in [('alwaysIncludeEmail', alwaysIncludeEmail), ('eventTypes', eventTypes), ('iCalUID', iCalUID), ('maxAttendees', maxAttendees), ('maxResults', maxResults), ('orderBy', orderBy), ('pageToken', pageToken), ('privateExtendedProperty', privateExtendedProperty), ('q', q), ('sharedExtendedProperty', sharedExtendedProperty), ('showDeleted', showDeleted), ('showHiddenInvitations', showHiddenInvitations), ('singleEvents', singleEvents), ('syncToken', syncToken), ('timeMax', timeMax), ('timeMin', timeMin), ('timeZone', timeZone), ('updatedMin', updatedMin), ('alt', alt), ('fields', fields), ('key', key), ('oauth_token', oauth_token), ('prettyPrint', prettyPrint), ('quotaUser', quotaUser), ('userIp', userIp)] if v is not None}
        response = self._post(url, data=request_body, params=query_params)
        response.raise_for_status()
        return response.json()

    def get_calendar(self, calendarId, alt=None, fields=None, key=None, oauth_token=None, prettyPrint=None, quotaUser=None, userIp=None) -> dict[str, Any]:
        """
        Get Calendar

        Args:
            calendarId (string): calendarId
            alt (string): Data format for the response. Example: 'json'.
            fields (string): Selector specifying which fields to include in a partial response. Example: 'amet in'.
            key (string): API key. Your API key identifies your project and provides you with API access, quota, and reports. Required unless you provide an OAuth 2.0 token. Example: 'amet in'.
            oauth_token (string): OAuth 2.0 token for the current user. Example: 'amet in'.
            prettyPrint (string): Returns response with indentations and line breaks. Example: 'true'.
            quotaUser (string): An opaque string that represents a user for quota purposes. Must not exceed 40 characters. Example: 'amet in'.
            userIp (string): Deprecated. Please use quotaUser instead. Example: 'amet in'.

        Returns:
            dict[str, Any]: Successful response

        Tags:
            calendars, {calendarId}
        """
        if calendarId is None:
            raise ValueError("Missing required parameter 'calendarId'")
        url = f"{self.base_url}/calendars/{calendarId}"
        query_params = {k: v for k, v in [('alt', alt), ('fields', fields), ('key', key), ('oauth_token', oauth_token), ('prettyPrint', prettyPrint), ('quotaUser', quotaUser), ('userIp', userIp)] if v is not None}
        response = self._get(url, params=query_params)
        response.raise_for_status()
        return response.json()

    def update_calendar(self, calendarId, alt=None, fields=None, key=None, oauth_token=None, prettyPrint=None, quotaUser=None, userIp=None, conferenceProperties=None, description=None, etag=None, id=None, kind=None, location=None, summary=None, timeZone=None) -> dict[str, Any]:
        """
        Update Calendar

        Args:
            calendarId (string): calendarId
            alt (string): Data format for the response. Example: 'json'.
            fields (string): Selector specifying which fields to include in a partial response. Example: 'amet in'.
            key (string): API key. Your API key identifies your project and provides you with API access, quota, and reports. Required unless you provide an OAuth 2.0 token. Example: 'amet in'.
            oauth_token (string): OAuth 2.0 token for the current user. Example: 'amet in'.
            prettyPrint (string): Returns response with indentations and line breaks. Example: 'true'.
            quotaUser (string): An opaque string that represents a user for quota purposes. Must not exceed 40 characters. Example: 'amet in'.
            userIp (string): Deprecated. Please use quotaUser instead. Example: 'amet in'.
            conferenceProperties (object): conferenceProperties
            description (string): description Example: 'officia enim aliquip ex'.
            etag (string): etag Example: 'labore adipisicing fugiat'.
            id (string): id Example: 'est pro'.
            kind (string): kind Example: 'calendar#calendar'.
            location (string): location Example: 'in voluptate commodo'.
            summary (string): summary Example: 'labore adipisicing enim'.
            timeZone (string): timeZone
                Example:
                ```json
                {
                  "conferenceProperties": {
                    "allowedConferenceSolutionTypes": [
                      "anim enim ut veniam",
                      "sit labore"
                    ]
                  },
                  "description": "officia enim aliquip ex",
                  "etag": "labore adipisicing fugiat",
                  "id": "est pro",
                  "kind": "calendar#calendar",
                  "location": "in voluptate commodo",
                  "summary": "labore adipisicing enim",
                  "timeZone": "cupidatat sed"
                }
                ```

        Returns:
            dict[str, Any]: Successful response

        Tags:
            calendars, {calendarId}
        """
        if calendarId is None:
            raise ValueError("Missing required parameter 'calendarId'")
        request_body = {
            'conferenceProperties': conferenceProperties,
            'description': description,
            'etag': etag,
            'id': id,
            'kind': kind,
            'location': location,
            'summary': summary,
            'timeZone': timeZone,
        }
        request_body = {k: v for k, v in request_body.items() if v is not None}
        url = f"{self.base_url}/calendars/{calendarId}"
        query_params = {k: v for k, v in [('alt', alt), ('fields', fields), ('key', key), ('oauth_token', oauth_token), ('prettyPrint', prettyPrint), ('quotaUser', quotaUser), ('userIp', userIp)] if v is not None}
        response = self._put(url, data=request_body, params=query_params)
        response.raise_for_status()
        return response.json()

    def delete_calendar(self, calendarId, alt=None, fields=None, key=None, oauth_token=None, prettyPrint=None, quotaUser=None, userIp=None) -> Any:
        """
        Delete Calendar

        Args:
            calendarId (string): calendarId
            alt (string): Data format for the response. Example: 'json'.
            fields (string): Selector specifying which fields to include in a partial response. Example: 'amet in'.
            key (string): API key. Your API key identifies your project and provides you with API access, quota, and reports. Required unless you provide an OAuth 2.0 token. Example: 'amet in'.
            oauth_token (string): OAuth 2.0 token for the current user. Example: 'amet in'.
            prettyPrint (string): Returns response with indentations and line breaks. Example: 'true'.
            quotaUser (string): An opaque string that represents a user for quota purposes. Must not exceed 40 characters. Example: 'amet in'.
            userIp (string): Deprecated. Please use quotaUser instead. Example: 'amet in'.

        Returns:
            Any: No Content

        Tags:
            calendars, {calendarId}
        """
        if calendarId is None:
            raise ValueError("Missing required parameter 'calendarId'")
        url = f"{self.base_url}/calendars/{calendarId}"
        query_params = {k: v for k, v in [('alt', alt), ('fields', fields), ('key', key), ('oauth_token', oauth_token), ('prettyPrint', prettyPrint), ('quotaUser', quotaUser), ('userIp', userIp)] if v is not None}
        response = self._delete(url, params=query_params)
        response.raise_for_status()
        return response.json()

    def patch_calendar(self, calendarId, alt=None, fields=None, key=None, oauth_token=None, prettyPrint=None, quotaUser=None, userIp=None, conferenceProperties=None, description=None, etag=None, id=None, kind=None, location=None, summary=None, timeZone=None) -> dict[str, Any]:
        """
        Patch Calendar

        Args:
            calendarId (string): calendarId
            alt (string): Data format for the response. Example: 'json'.
            fields (string): Selector specifying which fields to include in a partial response. Example: 'amet in'.
            key (string): API key. Your API key identifies your project and provides you with API access, quota, and reports. Required unless you provide an OAuth 2.0 token. Example: 'amet in'.
            oauth_token (string): OAuth 2.0 token for the current user. Example: 'amet in'.
            prettyPrint (string): Returns response with indentations and line breaks. Example: 'true'.
            quotaUser (string): An opaque string that represents a user for quota purposes. Must not exceed 40 characters. Example: 'amet in'.
            userIp (string): Deprecated. Please use quotaUser instead. Example: 'amet in'.
            conferenceProperties (object): conferenceProperties
            description (string): description Example: 'officia enim aliquip ex'.
            etag (string): etag Example: 'labore adipisicing fugiat'.
            id (string): id Example: 'est pro'.
            kind (string): kind Example: 'calendar#calendar'.
            location (string): location Example: 'in voluptate commodo'.
            summary (string): summary Example: 'labore adipisicing enim'.
            timeZone (string): timeZone
                Example:
                ```json
                {
                  "conferenceProperties": {
                    "allowedConferenceSolutionTypes": [
                      "anim enim ut veniam",
                      "sit labore"
                    ]
                  },
                  "description": "officia enim aliquip ex",
                  "etag": "labore adipisicing fugiat",
                  "id": "est pro",
                  "kind": "calendar#calendar",
                  "location": "in voluptate commodo",
                  "summary": "labore adipisicing enim",
                  "timeZone": "cupidatat sed"
                }
                ```

        Returns:
            dict[str, Any]: Successful response

        Tags:
            calendars, {calendarId}
        """
        if calendarId is None:
            raise ValueError("Missing required parameter 'calendarId'")
        request_body = {
            'conferenceProperties': conferenceProperties,
            'description': description,
            'etag': etag,
            'id': id,
            'kind': kind,
            'location': location,
            'summary': summary,
            'timeZone': timeZone,
        }
        request_body = {k: v for k, v in request_body.items() if v is not None}
        url = f"{self.base_url}/calendars/{calendarId}"
        query_params = {k: v for k, v in [('alt', alt), ('fields', fields), ('key', key), ('oauth_token', oauth_token), ('prettyPrint', prettyPrint), ('quotaUser', quotaUser), ('userIp', userIp)] if v is not None}
        response = self._patch(url, data=request_body, params=query_params)
        response.raise_for_status()
        return response.json()

    def clear_calendar(self, calendarId, alt=None, fields=None, key=None, oauth_token=None, prettyPrint=None, quotaUser=None, userIp=None) -> Any:
        """
        Clear Calendar

        Args:
            calendarId (string): calendarId
            alt (string): Data format for the response. Example: 'json'.
            fields (string): Selector specifying which fields to include in a partial response. Example: 'amet in'.
            key (string): API key. Your API key identifies your project and provides you with API access, quota, and reports. Required unless you provide an OAuth 2.0 token. Example: 'amet in'.
            oauth_token (string): OAuth 2.0 token for the current user. Example: 'amet in'.
            prettyPrint (string): Returns response with indentations and line breaks. Example: 'true'.
            quotaUser (string): An opaque string that represents a user for quota purposes. Must not exceed 40 characters. Example: 'amet in'.
            userIp (string): Deprecated. Please use quotaUser instead. Example: 'amet in'.

        Returns:
            Any: No Content

        Tags:
            calendars, {calendarId}
        """
        if calendarId is None:
            raise ValueError("Missing required parameter 'calendarId'")
        url = f"{self.base_url}/calendars/{calendarId}/clear"
        query_params = {k: v for k, v in [('alt', alt), ('fields', fields), ('key', key), ('oauth_token', oauth_token), ('prettyPrint', prettyPrint), ('quotaUser', quotaUser), ('userIp', userIp)] if v is not None}
        response = self._post(url, data={}, params=query_params)
        response.raise_for_status()
        return response.json()

    def calendar(self, alt=None, fields=None, key=None, oauth_token=None, prettyPrint=None, quotaUser=None, userIp=None, conferenceProperties=None, description=None, etag=None, id=None, kind=None, location=None, summary=None, timeZone=None) -> dict[str, Any]:
        """
        Calendar

        Args:
            alt (string): Data format for the response. Example: 'json'.
            fields (string): Selector specifying which fields to include in a partial response. Example: 'amet in'.
            key (string): API key. Your API key identifies your project and provides you with API access, quota, and reports. Required unless you provide an OAuth 2.0 token. Example: 'amet in'.
            oauth_token (string): OAuth 2.0 token for the current user. Example: 'amet in'.
            prettyPrint (string): Returns response with indentations and line breaks. Example: 'true'.
            quotaUser (string): An opaque string that represents a user for quota purposes. Must not exceed 40 characters. Example: 'amet in'.
            userIp (string): Deprecated. Please use quotaUser instead. Example: 'amet in'.
            conferenceProperties (object): conferenceProperties
            description (string): description Example: 'officia enim aliquip ex'.
            etag (string): etag Example: 'labore adipisicing fugiat'.
            id (string): id Example: 'est pro'.
            kind (string): kind Example: 'calendar#calendar'.
            location (string): location Example: 'in voluptate commodo'.
            summary (string): summary Example: 'labore adipisicing enim'.
            timeZone (string): timeZone
                Example:
                ```json
                {
                  "conferenceProperties": {
                    "allowedConferenceSolutionTypes": [
                      "anim enim ut veniam",
                      "sit labore"
                    ]
                  },
                  "description": "officia enim aliquip ex",
                  "etag": "labore adipisicing fugiat",
                  "id": "est pro",
                  "kind": "calendar#calendar",
                  "location": "in voluptate commodo",
                  "summary": "labore adipisicing enim",
                  "timeZone": "cupidatat sed"
                }
                ```

        Returns:
            dict[str, Any]: Successful response

        Tags:
            calendars
        """
        request_body = {
            'conferenceProperties': conferenceProperties,
            'description': description,
            'etag': etag,
            'id': id,
            'kind': kind,
            'location': location,
            'summary': summary,
            'timeZone': timeZone,
        }
        request_body = {k: v for k, v in request_body.items() if v is not None}
        url = f"{self.base_url}/calendars"
        query_params = {k: v for k, v in [('alt', alt), ('fields', fields), ('key', key), ('oauth_token', oauth_token), ('prettyPrint', prettyPrint), ('quotaUser', quotaUser), ('userIp', userIp)] if v is not None}
        response = self._post(url, data=request_body, params=query_params)
        response.raise_for_status()
        return response.json()

    def get_calendar_list(self, calendarId, alt=None, fields=None, key=None, oauth_token=None, prettyPrint=None, quotaUser=None, userIp=None) -> dict[str, Any]:
        """
        Get Calendar List

        Args:
            calendarId (string): calendarId
            alt (string): Data format for the response. Example: 'json'.
            fields (string): Selector specifying which fields to include in a partial response. Example: 'amet in'.
            key (string): API key. Your API key identifies your project and provides you with API access, quota, and reports. Required unless you provide an OAuth 2.0 token. Example: 'amet in'.
            oauth_token (string): OAuth 2.0 token for the current user. Example: 'amet in'.
            prettyPrint (string): Returns response with indentations and line breaks. Example: 'true'.
            quotaUser (string): An opaque string that represents a user for quota purposes. Must not exceed 40 characters. Example: 'amet in'.
            userIp (string): Deprecated. Please use quotaUser instead. Example: 'amet in'.

        Returns:
            dict[str, Any]: Successful response

        Tags:
            users/me, Calendar List
        """
        if calendarId is None:
            raise ValueError("Missing required parameter 'calendarId'")
        url = f"{self.base_url}/users/me/calendarList/{calendarId}"
        query_params = {k: v for k, v in [('alt', alt), ('fields', fields), ('key', key), ('oauth_token', oauth_token), ('prettyPrint', prettyPrint), ('quotaUser', quotaUser), ('userIp', userIp)] if v is not None}
        response = self._get(url, params=query_params)
        response.raise_for_status()
        return response.json()

    def update_calendar_list(self, calendarId, colorRgbFormat=None, alt=None, fields=None, key=None, oauth_token=None, prettyPrint=None, quotaUser=None, userIp=None, accessRole=None, backgroundColor=None, colorId=None, conferenceProperties=None, defaultReminders=None, deleted=None, description=None, etag=None, foregroundColor=None, hidden=None, id=None, kind=None, location=None, notificationSettings=None, primary=None, selected=None, summary=None, summaryOverride=None, timeZone=None) -> dict[str, Any]:
        """
        Update Calendar List

        Args:
            calendarId (string): calendarId
            colorRgbFormat (string): No description provided. Example: 'true'.
            alt (string): Data format for the response. Example: 'json'.
            fields (string): Selector specifying which fields to include in a partial response. Example: 'amet in'.
            key (string): API key. Your API key identifies your project and provides you with API access, quota, and reports. Required unless you provide an OAuth 2.0 token. Example: 'amet in'.
            oauth_token (string): OAuth 2.0 token for the current user. Example: 'amet in'.
            prettyPrint (string): Returns response with indentations and line breaks. Example: 'true'.
            quotaUser (string): An opaque string that represents a user for quota purposes. Must not exceed 40 characters. Example: 'amet in'.
            userIp (string): Deprecated. Please use quotaUser instead. Example: 'amet in'.
            accessRole (string): accessRole Example: 'eiusmod eu in Ut'.
            backgroundColor (string): backgroundColor Example: 'incididunt velit ipsum'.
            colorId (string): colorId Example: 'officia'.
            conferenceProperties (object): conferenceProperties
            defaultReminders (array): defaultReminders Example: "[{'method': 'adipisicing aute ex do', 'minutes': -38063085}, {'method': 'velit do', 'minutes': -43207232}]".
            deleted (string): deleted Example: 'false'.
            description (string): description Example: 'qui tempor in mollit eu'.
            etag (string): etag Example: 'deserunt enim nostrud est'.
            foregroundColor (string): foregroundColor Example: 'qui consequat Excepteur aliqua'.
            hidden (string): hidden Example: 'false'.
            id (string): id Example: 'in'.
            kind (string): kind Example: 'calendar#calendarListEntry'.
            location (string): location Example: 'exercitation dolore Ut sit'.
            notificationSettings (object): notificationSettings
            primary (string): primary Example: 'false'.
            selected (string): selected Example: 'false'.
            summary (string): summary Example: 'minim voluptate esse'.
            summaryOverride (string): summaryOverride Example: 'est dolor eu laborum'.
            timeZone (string): timeZone
                Example:
                ```json
                {
                  "accessRole": "eiusmod eu in Ut",
                  "backgroundColor": "incididunt velit ipsum",
                  "colorId": "officia",
                  "conferenceProperties": {
                    "allowedConferenceSolutionTypes": [
                      "sint in velit",
                      "veniam voluptate ut"
                    ]
                  },
                  "defaultReminders": [
                    {
                      "method": "adipisicing aute ex do",
                      "minutes": -38063085
                    },
                    {
                      "method": "velit do",
                      "minutes": -43207232
                    }
                  ],
                  "deleted": "false",
                  "description": "qui tempor in mollit eu",
                  "etag": "deserunt enim nostrud est",
                  "foregroundColor": "qui consequat Excepteur aliqua",
                  "hidden": "false",
                  "id": "in",
                  "kind": "calendar#calendarListEntry",
                  "location": "exercitation dolore Ut sit",
                  "notificationSettings": {
                    "notifications": [
                      {
                        "method": "consequa",
                        "type": "minim laborum"
                      },
                      {
                        "method": "magna adipisicing deserunt reprehenderit",
                        "type": "consequat consectetur ut"
                      }
                    ]
                  },
                  "primary": "false",
                  "selected": "false",
                  "summary": "minim voluptate esse",
                  "summaryOverride": "est dolor eu laborum",
                  "timeZone": "dolor commodo qui officia"
                }
                ```

        Returns:
            dict[str, Any]: Successful response

        Tags:
            users/me, Calendar List
        """
        if calendarId is None:
            raise ValueError("Missing required parameter 'calendarId'")
        request_body = {
            'accessRole': accessRole,
            'backgroundColor': backgroundColor,
            'colorId': colorId,
            'conferenceProperties': conferenceProperties,
            'defaultReminders': defaultReminders,
            'deleted': deleted,
            'description': description,
            'etag': etag,
            'foregroundColor': foregroundColor,
            'hidden': hidden,
            'id': id,
            'kind': kind,
            'location': location,
            'notificationSettings': notificationSettings,
            'primary': primary,
            'selected': selected,
            'summary': summary,
            'summaryOverride': summaryOverride,
            'timeZone': timeZone,
        }
        request_body = {k: v for k, v in request_body.items() if v is not None}
        url = f"{self.base_url}/users/me/calendarList/{calendarId}"
        query_params = {k: v for k, v in [('colorRgbFormat', colorRgbFormat), ('alt', alt), ('fields', fields), ('key', key), ('oauth_token', oauth_token), ('prettyPrint', prettyPrint), ('quotaUser', quotaUser), ('userIp', userIp)] if v is not None}
        response = self._put(url, data=request_body, params=query_params)
        response.raise_for_status()
        return response.json()

    def remove_calendar_on_list(self, calendarId, alt=None, fields=None, key=None, oauth_token=None, prettyPrint=None, quotaUser=None, userIp=None) -> Any:
        """
        Remove Calendar on List

        Args:
            calendarId (string): calendarId
            alt (string): Data format for the response. Example: 'json'.
            fields (string): Selector specifying which fields to include in a partial response. Example: 'amet in'.
            key (string): API key. Your API key identifies your project and provides you with API access, quota, and reports. Required unless you provide an OAuth 2.0 token. Example: 'amet in'.
            oauth_token (string): OAuth 2.0 token for the current user. Example: 'amet in'.
            prettyPrint (string): Returns response with indentations and line breaks. Example: 'true'.
            quotaUser (string): An opaque string that represents a user for quota purposes. Must not exceed 40 characters. Example: 'amet in'.
            userIp (string): Deprecated. Please use quotaUser instead. Example: 'amet in'.

        Returns:
            Any: No Content

        Tags:
            users/me, Calendar List
        """
        if calendarId is None:
            raise ValueError("Missing required parameter 'calendarId'")
        url = f"{self.base_url}/users/me/calendarList/{calendarId}"
        query_params = {k: v for k, v in [('alt', alt), ('fields', fields), ('key', key), ('oauth_token', oauth_token), ('prettyPrint', prettyPrint), ('quotaUser', quotaUser), ('userIp', userIp)] if v is not None}
        response = self._delete(url, params=query_params)
        response.raise_for_status()
        return response.json()

    def patch_calendar_list(self, calendarId, colorRgbFormat=None, alt=None, fields=None, key=None, oauth_token=None, prettyPrint=None, quotaUser=None, userIp=None, accessRole=None, backgroundColor=None, colorId=None, conferenceProperties=None, defaultReminders=None, deleted=None, description=None, etag=None, foregroundColor=None, hidden=None, id=None, kind=None, location=None, notificationSettings=None, primary=None, selected=None, summary=None, summaryOverride=None, timeZone=None) -> dict[str, Any]:
        """
        Patch Calendar List

        Args:
            calendarId (string): calendarId
            colorRgbFormat (string): No description provided. Example: 'true'.
            alt (string): Data format for the response. Example: 'json'.
            fields (string): Selector specifying which fields to include in a partial response. Example: 'amet in'.
            key (string): API key. Your API key identifies your project and provides you with API access, quota, and reports. Required unless you provide an OAuth 2.0 token. Example: 'amet in'.
            oauth_token (string): OAuth 2.0 token for the current user. Example: 'amet in'.
            prettyPrint (string): Returns response with indentations and line breaks. Example: 'true'.
            quotaUser (string): An opaque string that represents a user for quota purposes. Must not exceed 40 characters. Example: 'amet in'.
            userIp (string): Deprecated. Please use quotaUser instead. Example: 'amet in'.
            accessRole (string): accessRole Example: 'eiusmod eu in Ut'.
            backgroundColor (string): backgroundColor Example: 'incididunt velit ipsum'.
            colorId (string): colorId Example: 'officia'.
            conferenceProperties (object): conferenceProperties
            defaultReminders (array): defaultReminders Example: "[{'method': 'adipisicing aute ex do', 'minutes': -38063085}, {'method': 'velit do', 'minutes': -43207232}]".
            deleted (string): deleted Example: 'false'.
            description (string): description Example: 'qui tempor in mollit eu'.
            etag (string): etag Example: 'deserunt enim nostrud est'.
            foregroundColor (string): foregroundColor Example: 'qui consequat Excepteur aliqua'.
            hidden (string): hidden Example: 'false'.
            id (string): id Example: 'in'.
            kind (string): kind Example: 'calendar#calendarListEntry'.
            location (string): location Example: 'exercitation dolore Ut sit'.
            notificationSettings (object): notificationSettings
            primary (string): primary Example: 'false'.
            selected (string): selected Example: 'false'.
            summary (string): summary Example: 'minim voluptate esse'.
            summaryOverride (string): summaryOverride Example: 'est dolor eu laborum'.
            timeZone (string): timeZone
                Example:
                ```json
                {
                  "accessRole": "eiusmod eu in Ut",
                  "backgroundColor": "incididunt velit ipsum",
                  "colorId": "officia",
                  "conferenceProperties": {
                    "allowedConferenceSolutionTypes": [
                      "sint in velit",
                      "veniam voluptate ut"
                    ]
                  },
                  "defaultReminders": [
                    {
                      "method": "adipisicing aute ex do",
                      "minutes": -38063085
                    },
                    {
                      "method": "velit do",
                      "minutes": -43207232
                    }
                  ],
                  "deleted": "false",
                  "description": "qui tempor in mollit eu",
                  "etag": "deserunt enim nostrud est",
                  "foregroundColor": "qui consequat Excepteur aliqua",
                  "hidden": "false",
                  "id": "in",
                  "kind": "calendar#calendarListEntry",
                  "location": "exercitation dolore Ut sit",
                  "notificationSettings": {
                    "notifications": [
                      {
                        "method": "consequa",
                        "type": "minim laborum"
                      },
                      {
                        "method": "magna adipisicing deserunt reprehenderit",
                        "type": "consequat consectetur ut"
                      }
                    ]
                  },
                  "primary": "false",
                  "selected": "false",
                  "summary": "minim voluptate esse",
                  "summaryOverride": "est dolor eu laborum",
                  "timeZone": "dolor commodo qui officia"
                }
                ```

        Returns:
            dict[str, Any]: Successful response

        Tags:
            users/me, Calendar List
        """
        if calendarId is None:
            raise ValueError("Missing required parameter 'calendarId'")
        request_body = {
            'accessRole': accessRole,
            'backgroundColor': backgroundColor,
            'colorId': colorId,
            'conferenceProperties': conferenceProperties,
            'defaultReminders': defaultReminders,
            'deleted': deleted,
            'description': description,
            'etag': etag,
            'foregroundColor': foregroundColor,
            'hidden': hidden,
            'id': id,
            'kind': kind,
            'location': location,
            'notificationSettings': notificationSettings,
            'primary': primary,
            'selected': selected,
            'summary': summary,
            'summaryOverride': summaryOverride,
            'timeZone': timeZone,
        }
        request_body = {k: v for k, v in request_body.items() if v is not None}
        url = f"{self.base_url}/users/me/calendarList/{calendarId}"
        query_params = {k: v for k, v in [('colorRgbFormat', colorRgbFormat), ('alt', alt), ('fields', fields), ('key', key), ('oauth_token', oauth_token), ('prettyPrint', prettyPrint), ('quotaUser', quotaUser), ('userIp', userIp)] if v is not None}
        response = self._patch(url, data=request_body, params=query_params)
        response.raise_for_status()
        return response.json()

    def insert_calendar_on_list(self, colorRgbFormat=None, alt=None, fields=None, key=None, oauth_token=None, prettyPrint=None, quotaUser=None, userIp=None, accessRole=None, backgroundColor=None, colorId=None, conferenceProperties=None, defaultReminders=None, deleted=None, description=None, etag=None, foregroundColor=None, hidden=None, id=None, kind=None, location=None, notificationSettings=None, primary=None, selected=None, summary=None, summaryOverride=None, timeZone=None) -> dict[str, Any]:
        """
        Insert Calendar on List

        Args:
            colorRgbFormat (string): No description provided. Example: 'true'.
            alt (string): Data format for the response. Example: 'json'.
            fields (string): Selector specifying which fields to include in a partial response. Example: 'amet in'.
            key (string): API key. Your API key identifies your project and provides you with API access, quota, and reports. Required unless you provide an OAuth 2.0 token. Example: 'amet in'.
            oauth_token (string): OAuth 2.0 token for the current user. Example: 'amet in'.
            prettyPrint (string): Returns response with indentations and line breaks. Example: 'true'.
            quotaUser (string): An opaque string that represents a user for quota purposes. Must not exceed 40 characters. Example: 'amet in'.
            userIp (string): Deprecated. Please use quotaUser instead. Example: 'amet in'.
            accessRole (string): accessRole Example: 'eiusmod eu in Ut'.
            backgroundColor (string): backgroundColor Example: 'incididunt velit ipsum'.
            colorId (string): colorId Example: 'officia'.
            conferenceProperties (object): conferenceProperties
            defaultReminders (array): defaultReminders Example: "[{'method': 'adipisicing aute ex do', 'minutes': -38063085}, {'method': 'velit do', 'minutes': -43207232}]".
            deleted (string): deleted Example: 'false'.
            description (string): description Example: 'qui tempor in mollit eu'.
            etag (string): etag Example: 'deserunt enim nostrud est'.
            foregroundColor (string): foregroundColor Example: 'qui consequat Excepteur aliqua'.
            hidden (string): hidden Example: 'false'.
            id (string): id Example: 'in'.
            kind (string): kind Example: 'calendar#calendarListEntry'.
            location (string): location Example: 'exercitation dolore Ut sit'.
            notificationSettings (object): notificationSettings
            primary (string): primary Example: 'false'.
            selected (string): selected Example: 'false'.
            summary (string): summary Example: 'minim voluptate esse'.
            summaryOverride (string): summaryOverride Example: 'est dolor eu laborum'.
            timeZone (string): timeZone
                Example:
                ```json
                {
                  "accessRole": "eiusmod eu in Ut",
                  "backgroundColor": "incididunt velit ipsum",
                  "colorId": "officia",
                  "conferenceProperties": {
                    "allowedConferenceSolutionTypes": [
                      "sint in velit",
                      "veniam voluptate ut"
                    ]
                  },
                  "defaultReminders": [
                    {
                      "method": "adipisicing aute ex do",
                      "minutes": -38063085
                    },
                    {
                      "method": "velit do",
                      "minutes": -43207232
                    }
                  ],
                  "deleted": "false",
                  "description": "qui tempor in mollit eu",
                  "etag": "deserunt enim nostrud est",
                  "foregroundColor": "qui consequat Excepteur aliqua",
                  "hidden": "false",
                  "id": "in",
                  "kind": "calendar#calendarListEntry",
                  "location": "exercitation dolore Ut sit",
                  "notificationSettings": {
                    "notifications": [
                      {
                        "method": "consequa",
                        "type": "minim laborum"
                      },
                      {
                        "method": "magna adipisicing deserunt reprehenderit",
                        "type": "consequat consectetur ut"
                      }
                    ]
                  },
                  "primary": "false",
                  "selected": "false",
                  "summary": "minim voluptate esse",
                  "summaryOverride": "est dolor eu laborum",
                  "timeZone": "dolor commodo qui officia"
                }
                ```

        Returns:
            dict[str, Any]: Successful response

        Tags:
            users/me, Calendar List
        """
        request_body = {
            'accessRole': accessRole,
            'backgroundColor': backgroundColor,
            'colorId': colorId,
            'conferenceProperties': conferenceProperties,
            'defaultReminders': defaultReminders,
            'deleted': deleted,
            'description': description,
            'etag': etag,
            'foregroundColor': foregroundColor,
            'hidden': hidden,
            'id': id,
            'kind': kind,
            'location': location,
            'notificationSettings': notificationSettings,
            'primary': primary,
            'selected': selected,
            'summary': summary,
            'summaryOverride': summaryOverride,
            'timeZone': timeZone,
        }
        request_body = {k: v for k, v in request_body.items() if v is not None}
        url = f"{self.base_url}/users/me/calendarList"
        query_params = {k: v for k, v in [('colorRgbFormat', colorRgbFormat), ('alt', alt), ('fields', fields), ('key', key), ('oauth_token', oauth_token), ('prettyPrint', prettyPrint), ('quotaUser', quotaUser), ('userIp', userIp)] if v is not None}
        response = self._post(url, data=request_body, params=query_params)
        response.raise_for_status()
        return response.json()

    def list_calendars(self, userId, maxResults=None, minAccessRole=None, pageToken=None, showDeleted=None, showHidden=None, syncToken=None, alt=None, fields=None, key=None, oauth_token=None, prettyPrint=None, quotaUser=None, userIp=None) -> dict[str, Any]:
        """
        List Calendars

        Args:
            userId (string): userId
            maxResults (string): No description provided. Example: '54806309'.
            minAccessRole (string): No description provided. Example: 'amet in'.
            pageToken (string): No description provided. Example: 'amet in'.
            showDeleted (string): No description provided. Example: 'true'.
            showHidden (string): No description provided. Example: 'true'.
            syncToken (string): No description provided. Example: 'amet in'.
            alt (string): Data format for the response. Example: 'json'.
            fields (string): Selector specifying which fields to include in a partial response. Example: 'amet in'.
            key (string): API key. Your API key identifies your project and provides you with API access, quota, and reports. Required unless you provide an OAuth 2.0 token. Example: 'amet in'.
            oauth_token (string): OAuth 2.0 token for the current user. Example: '{{accessToken}}'.
            prettyPrint (string): Returns response with indentations and line breaks. Example: 'true'.
            quotaUser (string): An opaque string that represents a user for quota purposes. Must not exceed 40 characters. Example: 'amet in'.
            userIp (string): Deprecated. Please use quotaUser instead. Example: 'amet in'.

        Returns:
            dict[str, Any]: Successful response

        Tags:
            users/me, Calendar List
        """
        if userId is None:
            raise ValueError("Missing required parameter 'userId'")
        url = f"{self.base_url}/users/{userId}/calendarList"
        query_params = {k: v for k, v in [('maxResults', maxResults), ('minAccessRole', minAccessRole), ('pageToken', pageToken), ('showDeleted', showDeleted), ('showHidden', showHidden), ('syncToken', syncToken), ('alt', alt), ('fields', fields), ('key', key), ('oauth_token', oauth_token), ('prettyPrint', prettyPrint), ('quotaUser', quotaUser), ('userIp', userIp)] if v is not None}
        response = self._get(url, params=query_params)
        response.raise_for_status()
        return response.json()

    def watch_calendar_list(self, maxResults=None, minAccessRole=None, pageToken=None, showDeleted=None, showHidden=None, syncToken=None, alt=None, fields=None, key=None, oauth_token=None, prettyPrint=None, quotaUser=None, userIp=None, address=None, expiration=None, id=None, kind=None, params=None, payload=None, resourceId=None, resourceUri=None, token=None, type=None) -> dict[str, Any]:
        """
        Watch Calendar List

        Args:
            maxResults (string): No description provided. Example: '54806309'.
            minAccessRole (string): No description provided. Example: 'amet in'.
            pageToken (string): No description provided. Example: 'amet in'.
            showDeleted (string): No description provided. Example: 'true'.
            showHidden (string): No description provided. Example: 'true'.
            syncToken (string): No description provided. Example: 'amet in'.
            alt (string): Data format for the response. Example: 'json'.
            fields (string): Selector specifying which fields to include in a partial response. Example: 'amet in'.
            key (string): API key. Your API key identifies your project and provides you with API access, quota, and reports. Required unless you provide an OAuth 2.0 token. Example: 'amet in'.
            oauth_token (string): OAuth 2.0 token for the current user. Example: 'amet in'.
            prettyPrint (string): Returns response with indentations and line breaks. Example: 'true'.
            quotaUser (string): An opaque string that represents a user for quota purposes. Must not exceed 40 characters. Example: 'amet in'.
            userIp (string): Deprecated. Please use quotaUser instead. Example: 'amet in'.
            address (string): address Example: 'incididunt sed consequat'.
            expiration (string): expiration Example: 'velit ad aliq'.
            id (string): id Example: 'velit eiusmod'.
            kind (string): kind Example: 'api#channel'.
            params (object): params
            payload (boolean): payload Example: 'False'.
            resourceId (string): resourceId Example: 'aute'.
            resourceUri (string): resourceUri Example: 'fugiat consequat'.
            token (string): token Example: 'ullamco officia in'.
            type (string): type
                Example:
                ```json
                {
                  "address": "incididunt sed consequat",
                  "expiration": "velit ad aliq",
                  "id": "velit eiusmod",
                  "kind": "api#channel",
                  "params": {
                    "reprehenderit5c": "non",
                    "sint_b": "cupidatat do"
                  },
                  "payload": false,
                  "resourceId": "aute",
                  "resourceUri": "fugiat consequat",
                  "token": "ullamco officia in",
                  "type": "ex eiusmod adipisicing mollit"
                }
                ```

        Returns:
            dict[str, Any]: Successful response

        Tags:
            users/me, Calendar List
        """
        request_body = {
            'address': address,
            'expiration': expiration,
            'id': id,
            'kind': kind,
            'params': params,
            'payload': payload,
            'resourceId': resourceId,
            'resourceUri': resourceUri,
            'token': token,
            'type': type,
        }
        request_body = {k: v for k, v in request_body.items() if v is not None}
        url = f"{self.base_url}/users/me/calendarList/watch"
        query_params = {k: v for k, v in [('maxResults', maxResults), ('minAccessRole', minAccessRole), ('pageToken', pageToken), ('showDeleted', showDeleted), ('showHidden', showHidden), ('syncToken', syncToken), ('alt', alt), ('fields', fields), ('key', key), ('oauth_token', oauth_token), ('prettyPrint', prettyPrint), ('quotaUser', quotaUser), ('userIp', userIp)] if v is not None}
        response = self._post(url, data=request_body, params=query_params)
        response.raise_for_status()
        return response.json()

    def list_calendar_settings(self, maxResults=None, pageToken=None, syncToken=None, alt=None, fields=None, key=None, oauth_token=None, prettyPrint=None, quotaUser=None, userIp=None) -> dict[str, Any]:
        """
        List Calendar Settings

        Args:
            maxResults (string): No description provided. Example: '54806309'.
            pageToken (string): No description provided. Example: 'amet in'.
            syncToken (string): No description provided. Example: 'amet in'.
            alt (string): Data format for the response. Example: 'json'.
            fields (string): Selector specifying which fields to include in a partial response. Example: 'amet in'.
            key (string): API key. Your API key identifies your project and provides you with API access, quota, and reports. Required unless you provide an OAuth 2.0 token. Example: 'amet in'.
            oauth_token (string): OAuth 2.0 token for the current user. Example: 'amet in'.
            prettyPrint (string): Returns response with indentations and line breaks. Example: 'true'.
            quotaUser (string): An opaque string that represents a user for quota purposes. Must not exceed 40 characters. Example: 'amet in'.
            userIp (string): Deprecated. Please use quotaUser instead. Example: 'amet in'.

        Returns:
            dict[str, Any]: Successful response

        Tags:
            users/me, settings
        """
        url = f"{self.base_url}/users/me/settings"
        query_params = {k: v for k, v in [('maxResults', maxResults), ('pageToken', pageToken), ('syncToken', syncToken), ('alt', alt), ('fields', fields), ('key', key), ('oauth_token', oauth_token), ('prettyPrint', prettyPrint), ('quotaUser', quotaUser), ('userIp', userIp)] if v is not None}
        response = self._get(url, params=query_params)
        response.raise_for_status()
        return response.json()

    def get_calendar_settings(self, setting, alt=None, fields=None, key=None, oauth_token=None, prettyPrint=None, quotaUser=None, userIp=None) -> dict[str, Any]:
        """
        Get Calendar Settings

        Args:
            setting (string): setting
            alt (string): Data format for the response. Example: 'json'.
            fields (string): Selector specifying which fields to include in a partial response. Example: 'amet in'.
            key (string): API key. Your API key identifies your project and provides you with API access, quota, and reports. Required unless you provide an OAuth 2.0 token. Example: 'amet in'.
            oauth_token (string): OAuth 2.0 token for the current user. Example: 'amet in'.
            prettyPrint (string): Returns response with indentations and line breaks. Example: 'true'.
            quotaUser (string): An opaque string that represents a user for quota purposes. Must not exceed 40 characters. Example: 'amet in'.
            userIp (string): Deprecated. Please use quotaUser instead. Example: 'amet in'.

        Returns:
            dict[str, Any]: Successful response

        Tags:
            users/me, settings
        """
        if setting is None:
            raise ValueError("Missing required parameter 'setting'")
        url = f"{self.base_url}/users/me/settings/{setting}"
        query_params = {k: v for k, v in [('alt', alt), ('fields', fields), ('key', key), ('oauth_token', oauth_token), ('prettyPrint', prettyPrint), ('quotaUser', quotaUser), ('userIp', userIp)] if v is not None}
        response = self._get(url, params=query_params)
        response.raise_for_status()
        return response.json()

    def watch_calendar_settings(self, maxResults=None, pageToken=None, syncToken=None, alt=None, fields=None, key=None, oauth_token=None, prettyPrint=None, quotaUser=None, userIp=None, address=None, expiration=None, id=None, kind=None, params=None, payload=None, resourceId=None, resourceUri=None, token=None, type=None) -> dict[str, Any]:
        """
        Watch Calendar Settings

        Args:
            maxResults (string): No description provided. Example: '54806309'.
            pageToken (string): No description provided. Example: 'amet in'.
            syncToken (string): No description provided. Example: 'amet in'.
            alt (string): Data format for the response. Example: 'json'.
            fields (string): Selector specifying which fields to include in a partial response. Example: 'amet in'.
            key (string): API key. Your API key identifies your project and provides you with API access, quota, and reports. Required unless you provide an OAuth 2.0 token. Example: 'amet in'.
            oauth_token (string): OAuth 2.0 token for the current user. Example: 'amet in'.
            prettyPrint (string): Returns response with indentations and line breaks. Example: 'true'.
            quotaUser (string): An opaque string that represents a user for quota purposes. Must not exceed 40 characters. Example: 'amet in'.
            userIp (string): Deprecated. Please use quotaUser instead. Example: 'amet in'.
            address (string): address Example: 'incididunt sed consequat'.
            expiration (string): expiration Example: 'velit ad aliq'.
            id (string): id Example: 'velit eiusmod'.
            kind (string): kind Example: 'api#channel'.
            params (object): params
            payload (boolean): payload Example: 'False'.
            resourceId (string): resourceId Example: 'aute'.
            resourceUri (string): resourceUri Example: 'fugiat consequat'.
            token (string): token Example: 'ullamco officia in'.
            type (string): type
                Example:
                ```json
                {
                  "address": "incididunt sed consequat",
                  "expiration": "velit ad aliq",
                  "id": "velit eiusmod",
                  "kind": "api#channel",
                  "params": {
                    "reprehenderit5c": "non",
                    "sint_b": "cupidatat do"
                  },
                  "payload": false,
                  "resourceId": "aute",
                  "resourceUri": "fugiat consequat",
                  "token": "ullamco officia in",
                  "type": "ex eiusmod adipisicing mollit"
                }
                ```

        Returns:
            dict[str, Any]: Successful response

        Tags:
            users/me, settings
        """
        request_body = {
            'address': address,
            'expiration': expiration,
            'id': id,
            'kind': kind,
            'params': params,
            'payload': payload,
            'resourceId': resourceId,
            'resourceUri': resourceUri,
            'token': token,
            'type': type,
        }
        request_body = {k: v for k, v in request_body.items() if v is not None}
        url = f"{self.base_url}/users/me/settings/watch"
        query_params = {k: v for k, v in [('maxResults', maxResults), ('pageToken', pageToken), ('syncToken', syncToken), ('alt', alt), ('fields', fields), ('key', key), ('oauth_token', oauth_token), ('prettyPrint', prettyPrint), ('quotaUser', quotaUser), ('userIp', userIp)] if v is not None}
        response = self._post(url, data=request_body, params=query_params)
        response.raise_for_status()
        return response.json()

    def stop_calendar_channel(self, alt=None, fields=None, key=None, oauth_token=None, prettyPrint=None, quotaUser=None, userIp=None, address=None, expiration=None, id=None, kind=None, params=None, payload=None, resourceId=None, resourceUri=None, token=None, type=None) -> Any:
        """
        Stop Calendar Channel

        Args:
            alt (string): Data format for the response. Example: 'json'.
            fields (string): Selector specifying which fields to include in a partial response. Example: 'amet in'.
            key (string): API key. Your API key identifies your project and provides you with API access, quota, and reports. Required unless you provide an OAuth 2.0 token. Example: 'amet in'.
            oauth_token (string): OAuth 2.0 token for the current user. Example: 'amet in'.
            prettyPrint (string): Returns response with indentations and line breaks. Example: 'true'.
            quotaUser (string): An opaque string that represents a user for quota purposes. Must not exceed 40 characters. Example: 'amet in'.
            userIp (string): Deprecated. Please use quotaUser instead. Example: 'amet in'.
            address (string): address Example: 'incididunt sed consequat'.
            expiration (string): expiration Example: 'velit ad aliq'.
            id (string): id Example: 'velit eiusmod'.
            kind (string): kind Example: 'api#channel'.
            params (object): params
            payload (boolean): payload Example: 'False'.
            resourceId (string): resourceId Example: 'aute'.
            resourceUri (string): resourceUri Example: 'fugiat consequat'.
            token (string): token Example: 'ullamco officia in'.
            type (string): type
                Example:
                ```json
                {
                  "address": "incididunt sed consequat",
                  "expiration": "velit ad aliq",
                  "id": "velit eiusmod",
                  "kind": "api#channel",
                  "params": {
                    "reprehenderit5c": "non",
                    "sint_b": "cupidatat do"
                  },
                  "payload": false,
                  "resourceId": "aute",
                  "resourceUri": "fugiat consequat",
                  "token": "ullamco officia in",
                  "type": "ex eiusmod adipisicing mollit"
                }
                ```

        Returns:
            Any: No Content
        """
        request_body = {
            'address': address,
            'expiration': expiration,
            'id': id,
            'kind': kind,
            'params': params,
            'payload': payload,
            'resourceId': resourceId,
            'resourceUri': resourceUri,
            'token': token,
            'type': type,
        }
        request_body = {k: v for k, v in request_body.items() if v is not None}
        url = f"{self.base_url}/channels/stop"
        query_params = {k: v for k, v in [('alt', alt), ('fields', fields), ('key', key), ('oauth_token', oauth_token), ('prettyPrint', prettyPrint), ('quotaUser', quotaUser), ('userIp', userIp)] if v is not None}
        response = self._post(url, data=request_body, params=query_params)
        response.raise_for_status()
        return response.json()

    def get_calendar_colors(self, alt=None, fields=None, key=None, oauth_token=None, prettyPrint=None, quotaUser=None, userIp=None) -> dict[str, Any]:
        """
        Get Calendar Colors

        Args:
            alt (string): Data format for the response. Example: 'json'.
            fields (string): Selector specifying which fields to include in a partial response. Example: 'amet in'.
            key (string): API key. Your API key identifies your project and provides you with API access, quota, and reports. Required unless you provide an OAuth 2.0 token. Example: 'amet in'.
            oauth_token (string): OAuth 2.0 token for the current user. Example: 'amet in'.
            prettyPrint (string): Returns response with indentations and line breaks. Example: 'true'.
            quotaUser (string): An opaque string that represents a user for quota purposes. Must not exceed 40 characters. Example: 'amet in'.
            userIp (string): Deprecated. Please use quotaUser instead. Example: 'amet in'.

        Returns:
            dict[str, Any]: Successful response
        """
        url = f"{self.base_url}/colors"
        query_params = {k: v for k, v in [('alt', alt), ('fields', fields), ('key', key), ('oauth_token', oauth_token), ('prettyPrint', prettyPrint), ('quotaUser', quotaUser), ('userIp', userIp)] if v is not None}
        response = self._get(url, params=query_params)
        response.raise_for_status()
        return response.json()

    def query_free_busy(self, alt=None, fields=None, key=None, oauth_token=None, prettyPrint=None, quotaUser=None, userIp=None, calendarExpansionMax=None, groupExpansionMax=None, items=None, timeMax=None, timeMin=None, timeZone=None) -> dict[str, Any]:
        """
        Query Free Busy

        Args:
            alt (string): Data format for the response. Example: 'json'.
            fields (string): Selector specifying which fields to include in a partial response. Example: 'amet in'.
            key (string): API key. Your API key identifies your project and provides you with API access, quota, and reports. Required unless you provide an OAuth 2.0 token. Example: 'amet in'.
            oauth_token (string): OAuth 2.0 token for the current user. Example: 'amet in'.
            prettyPrint (string): Returns response with indentations and line breaks. Example: 'true'.
            quotaUser (string): An opaque string that represents a user for quota purposes. Must not exceed 40 characters. Example: 'amet in'.
            userIp (string): Deprecated. Please use quotaUser instead. Example: 'amet in'.
            calendarExpansionMax (number): calendarExpansionMax Example: '37977981'.
            groupExpansionMax (number): groupExpansionMax Example: '-92198829'.
            items (array): items Example: "[{'id': 'qui labore velit in anim'}, {'id': 'sed dolore dolor laborum eiusmod'}]".
            timeMax (string): timeMax Example: '2016-10-26T20:45:39.467Z'.
            timeMin (string): timeMin Example: '1971-06-26T00:25:33.327Z'.
            timeZone (string): timeZone
                Example:
                ```json
                {
                  "calendarExpansionMax": 37977981,
                  "groupExpansionMax": -92198829,
                  "items": [
                    {
                      "id": "qui labore velit in anim"
                    },
                    {
                      "id": "sed dolore dolor laborum eiusmod"
                    }
                  ],
                  "timeMax": "2016-10-26T20:45:39.467Z",
                  "timeMin": "1971-06-26T00:25:33.327Z",
                  "timeZone": "UTC"
                }
                ```

        Returns:
            dict[str, Any]: Successful response
        """
        request_body = {
            'calendarExpansionMax': calendarExpansionMax,
            'groupExpansionMax': groupExpansionMax,
            'items': items,
            'timeMax': timeMax,
            'timeMin': timeMin,
            'timeZone': timeZone,
        }
        request_body = {k: v for k, v in request_body.items() if v is not None}
        url = f"{self.base_url}/freeBusy"
        query_params = {k: v for k, v in [('alt', alt), ('fields', fields), ('key', key), ('oauth_token', oauth_token), ('prettyPrint', prettyPrint), ('quotaUser', quotaUser), ('userIp', userIp)] if v is not None}
        response = self._post(url, data=request_body, params=query_params)
        response.raise_for_status()
        return response.json()

    def list_tools(self):
        return [
            self.get_event,
            self.get_today_events,
            self.list_events,
            self.quick_add_event,
            self.get_event_instances,
            # Auto Generated from Openapi spec
            self.get_access_control_rule,
            self.update_access_control_rule,
            self.delete_access_control_rule,
            self.patch_access_control_rule,
            self.return_access_control_rules,
            self.insert_access_control_rule,
            self.watch_access_control_rules,
            self.delete_event,
            self.insert_event,
            self.move_event,
            self.return_events_from_calendar,
            self.watch_events,
            self.get_calendar,
            self.update_calendar,
            self.delete_calendar,
            self.patch_calendar,
            self.clear_calendar,
            self.calendar,
            self.get_calendar_list,
            self.update_calendar_list,
            self.remove_calendar_on_list,
            self.patch_calendar_list,
            self.insert_calendar_on_list,
            self.list_calendars,
            self.watch_calendar_list,
            self.list_calendar_settings,
            self.get_calendar_settings,
            self.watch_calendar_settings,
            self.stop_calendar_channel,
            self.get_calendar_colors,
            self.query_free_busy
        ]
