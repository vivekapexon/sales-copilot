// Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
// SPDX-License-Identifier: MIT-0
import React, { forwardRef, useState } from "react";

import Avatar from "@cloudscape-design/chat-components/avatar";
import ButtonGroup, {
  type ButtonGroupProps,
} from "@cloudscape-design/components/button-group";
import StatusIndicator from "@cloudscape-design/components/status-indicator";

import { Box, Button, SpaceBetween } from "@cloudscape-design/components";
import type { AuthorAvatarProps } from "../config";

export function ChatBubbleAvatar({ type, name }: AuthorAvatarProps) {
  if (type === "gen-ai") {
    return (
      <svg
        xmlns="http://www.w3.org/2000/svg"
        width="24"
        height="28"
        viewBox="0 0 24 28"
        fill="none"
      >
        <path
          d="M8.92975 5.43617L9.73275 7.66617C10.6248 10.1412 12.5737 12.0902 15.0487 12.9822L17.2787 13.7852C17.4797 13.8582 17.4797 14.1432 17.2787 14.2152L15.0487 15.0182C12.5737 15.9102 10.6248 17.8592 9.73275 20.3342L8.92975 22.5642C8.85675 22.7652 8.57175 22.7652 8.49975 22.5642L7.69675 20.3342C6.80475 17.8592 4.85575 15.9102 2.38075 15.0182L0.15075 14.2152C-0.05025 14.1422 -0.05025 13.8572 0.15075 13.7852L2.38075 12.9822C4.85575 12.0902 6.80475 10.1412 7.69675 7.66617L8.49975 5.43617C8.57175 5.23417 8.85675 5.23417 8.92975 5.43617Z"
          fill="#006CE0"
        />
        <path
          d="M18.9678 0.07725L19.3748 1.20625C19.8268 2.45925 20.8138 3.44625 22.0668 3.89825L23.1958 4.30525C23.2978 4.34225 23.2978 4.48625 23.1958 4.52325L22.0668 4.93025C20.8138 5.38225 19.8268 6.36925 19.3748 7.62225L18.9678 8.75125C18.9308 8.85325 18.7868 8.85325 18.7498 8.75125L18.3428 7.62225C17.8908 6.36925 16.9038 5.38225 15.6508 4.93025L14.5218 4.52325C14.4198 4.48625 14.4198 4.34225 14.5218 4.30525L15.6508 3.89825C16.9038 3.44625 17.8908 2.45925 18.3428 1.20625L18.7498 0.07725C18.7868 -0.02575 18.9318 -0.02575 18.9678 0.07725Z"
          fill="#006CE0"
        />
        <path
          d="M18.9678 19.2503L19.3748 20.3793C19.8268 21.6323 20.8138 22.6193 22.0668 23.0713L23.1958 23.4783C23.2978 23.5153 23.2978 23.6593 23.1958 23.6963L22.0668 24.1033C20.8138 24.5553 19.8268 25.5423 19.3748 26.7953L18.9678 27.9243C18.9308 28.0263 18.7868 28.0263 18.7498 27.9243L18.3428 26.7953C17.8908 25.5423 16.9038 24.5553 15.6508 24.1033L14.5218 23.6963C14.4198 23.6593 14.4198 23.5153 14.5218 23.4783L15.6508 23.0713C16.9038 22.6193 17.8908 21.6323 18.3428 20.3793L18.7498 19.2503C18.7868 19.1483 18.9318 19.1483 18.9678 19.2503Z"
          fill="#006CE0"
        />
      </svg>
    );
    // return <Avatar color="gen-ai" iconName="gen-ai" tooltipText={name} ariaLabel={name} loading={loading} />;
  }

  return (
    <Avatar
      iconName="user-profile-active"
      // initials={initials}
      tooltipText={name}
      ariaLabel={name}
    />
  );
}

export function CodeViewActions({ contentToCopy }: { contentToCopy: string }) {
  return (
    <ButtonGroup
      ariaLabel="Code snippet actions"
      variant="icon"
      onItemClick={({ detail }) => {
        if (detail.id !== "copy" || !navigator.clipboard) {
          return;
        }

        // eslint-disable-next-line no-console
        navigator.clipboard
          .writeText(contentToCopy)
          .catch((error) => console.log("Failed to copy", error.message));
      }}
      items={[
        {
          type: "group",
          text: "Feedback",
          items: [
            {
              type: "icon-button",
              id: "run-command",
              iconName: "play",
              text: "Run command",
            },
            {
              type: "icon-button",
              id: "send-cloudshell",
              iconName: "script",
              text: "Send to IDE",
            },
          ],
        },
        {
          type: "icon-button",
          id: "copy",
          iconName: "copy",
          text: "Copy",
          popoverFeedback: (
            <StatusIndicator type="success">Message copied</StatusIndicator>
          ),
        },
      ]}
    />
  );
}

export const FittedContainer = ({
  children,
}: {
  children: React.ReactNode;
}) => {
  return (
    <div style={{ position: "relative", flexGrow: 1 }}>
      <div style={{ position: "absolute", inset: 0 }}>{children}</div>
    </div>
  );
};

export const ScrollableContainer = forwardRef(function ScrollableContainer(
  { children }: { children: React.ReactNode },
  ref: React.Ref<HTMLDivElement>
) {
  return (
    <div style={{ position: "relative", blockSize: "100%" }}>
      <div
        style={{ position: "absolute", inset: 0, overflowY: "auto" }}
        ref={ref}
        data-testid="chat-scroll-container"
      >
        {children}
      </div>
    </div>
  );
});
export const ScrollableList = forwardRef(function ScrollableContainer(
  { children }: { children: React.ReactNode },
  ref: React.Ref<HTMLDivElement>
) {
  return (
    <div style={{ position: "relative", blockSize: "100%" }}>
      <div
        style={{ position: "absolute", maxHeight: 310, overflowY: "auto" }}
        ref={ref}
        data-testid="list-scroll-container"
      >
        {children}
      </div>
    </div>
  );
});

export function FeedbackActions({
  contentToCopy,
  onNotHelpfulFeedback,
}: {
  contentToCopy: string;
  onNotHelpfulFeedback: () => void;
}) {
  const [feedback, setFeedback] = useState<string>("");
  const [feedbackSubmitting, setFeedbackSubmitting] = useState<string>("");

  const items: ButtonGroupProps.ItemOrGroup[] = [
    {
      type: "group",
      text: "Vote",
      items: [
        {
          type: "icon-button",
          id: "helpful",
          iconName: feedback === "helpful" ? "thumbs-up-filled" : "thumbs-up",
          text: "Helpful",
          disabled: !!feedback.length || feedbackSubmitting === "not-helpful",
          disabledReason: feedbackSubmitting.length
            ? ""
            : feedback === "helpful"
            ? '"Helpful" feedback has been submitted.'
            : '"Helpful" option is unavailable after "Not helpful" feedback submitted.',
          loading: feedbackSubmitting === "helpful",
          popoverFeedback:
            feedback === "helpful" ? (
              <StatusIndicator type="success">
                Feedback submitted
              </StatusIndicator>
            ) : (
              "Submitting feedback"
            ),
        },
        {
          type: "icon-button",
          id: "not-helpful",
          iconName:
            feedback === "not-helpful" ? "thumbs-down-filled" : "thumbs-down",
          text: "Not helpful",
          disabled: !!feedback.length || feedbackSubmitting === "helpful",
          disabledReason: feedbackSubmitting.length
            ? ""
            : feedback === "not-helpful"
            ? '"Not helpful" feedback has been submitted.'
            : '"Not helpful" option is unavailable after "Helpful" feedback submitted.',
          loading: feedbackSubmitting === "not-helpful",
          popoverFeedback:
            feedback === "helpful" ? (
              <StatusIndicator type="success">
                Feedback submitted
              </StatusIndicator>
            ) : (
              "Submitting feedback"
            ),
        },
      ],
    },
    {
      type: "icon-button",
      id: "copy",
      iconName: "copy",
      text: "Copy",
      popoverFeedback: (
        <StatusIndicator type="success">Message copied</StatusIndicator>
      ),
    },
  ];

  return (
    <ButtonGroup
      ariaLabel="Chat actions"
      variant="icon"
      items={items}
      onItemClick={({ detail }) => {
        if (detail.id === "copy" && navigator.clipboard) {
          return (
            navigator.clipboard
              .writeText(contentToCopy)
              // eslint-disable-next-line no-console
              .catch((error) => console.log("Failed to copy", error.message))
          );
        }

        setFeedbackSubmitting(detail.id);

        setTimeout(() => {
          setFeedback(detail.id);
          setFeedbackSubmitting("");
          if (detail.id === "not-helpful") {
            onNotHelpfulFeedback();
          }
        }, 2000);
      }}
    />
  );
}

export const TableEmptyState = ({ resourceName }: { resourceName: string }) => (
  <Box margin={{ vertical: "xs" }} textAlign="center" color="inherit">
    <SpaceBetween size="xxs">
      <div>
        <b>No {resourceName.toLowerCase()}s</b>
        <Box variant="p" color="inherit">
          No {resourceName.toLowerCase()}s associated with this resource.
        </Box>
      </div>
      <Button>Create {resourceName.toLowerCase()}</Button>
    </SpaceBetween>
  </Box>
);

export const TableNoMatchState = ({
  onClearFilter,
}: {
  onClearFilter: () => void;
}) => (
  <Box margin={{ vertical: "xs" }} textAlign="center" color="inherit">
    <SpaceBetween size="xxs">
      <div>
        <b>No matches</b>
        <Box variant="p" color="inherit">
          We can't find a match.
        </Box>
      </div>
      <Button onClick={onClearFilter}>Clear filter</Button>
    </SpaceBetween>
  </Box>
);
