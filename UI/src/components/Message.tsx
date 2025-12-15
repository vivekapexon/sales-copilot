// Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
// SPDX-License-Identifier: MIT-0

import ChatBubble from "@cloudscape-design/chat-components/chat-bubble";
import Alert from "@cloudscape-design/components/alert";
import FileTokenGroup from "@cloudscape-design/components/file-token-group";
import LiveRegion from "@cloudscape-design/components/live-region";
import SpaceBetween from "@cloudscape-design/components/space-between";

// import FeedbackDialog from "./feedback-dialog";
import {
  AUTHORS,
  fileTokenGroupI18nStrings,
  type Message,
  supportPromptItems,
} from "../config";

import "../chat.scss";
import {
  ChatBubbleAvatar,
  CodeViewActions,
  //   FeedbackActions,
} from "./Common";
import Markdown from "react-markdown";
import remarkGfm from "remark-gfm";

export default function Messages({
  messages = [],
}: {
  messages: Array<Message>;
  addMessage: (index: number, message: Message) => void;
}) {
  const latestMessage: Message = messages[messages.length - 1];

  const promptText = supportPromptItems.map((item) => item.text);

  return (
    <div className="messages" role="region" aria-label="Chat">
      <LiveRegion hidden={true} assertive={latestMessage?.type === "alert"}>
        {latestMessage?.type === "alert" && latestMessage.header}
        {latestMessage?.content}
        {latestMessage?.type === "chat-bubble" &&
          latestMessage.supportPrompts &&
          `There are ${promptText.length} support prompts accompanying this message. ${promptText}`}
      </LiveRegion>

      {messages.map((message, index) => {
        if (message.type === "alert") {
          return (
            <Alert
              key={"error-alert" + index}
              header={message.header}
              type="error"
              statusIconAriaLabel="Error"
              data-testid={"error-alert" + index}
            >
              {message.content}
            </Alert>
          );
        }

        if (message.type === "LineChart") {
          return message.content;
        }

        const author = AUTHORS[message?.authorId || 0];

        return (
          <SpaceBetween
            size="xs"
            key={"" + message.authorId + message.timestamp + index}
          >
            <ChatBubble
              avatar={
                <ChatBubbleAvatar {...author} loading={message.avatarLoading} />
              }
              ariaLabel={`${author?.name} at ${message.timestamp}`}
              type={author?.type === "gen-ai" ? "incoming" : "outgoing"}
              hideAvatar={message.hideAvatar}
              actions={
                message.actions === "code-view" ? (
                  <CodeViewActions
                    contentToCopy={message.contentToCopy || ""}
                  />
                ) : message.actions === "feedback" ? (
                  //   <FeedbackActions
                  //     contentToCopy={message.contentToCopy || ""}
                  //     onNotHelpfulFeedback={() =>
                  //       setShowFeedbackDialog(index, true)
                  //     }
                  //   />
                  <></>
                ) : null
              }
            >
              <SpaceBetween size="xs">
                <div
                  key={"" + message?.authorId + message?.timestamp + "content"}
                >
                  {message.authorId?.toLowerCase() == "user" ? (
                    <>{message.content}</>
                  ) : (
                    <Markdown
                      remarkPlugins={[remarkGfm]}
                    >{`${message.content}`}</Markdown>
                  )}
                </div>
                {message.files && message.files.length > 0 && (
                  <FileTokenGroup
                    readOnly
                    items={message.files.map((file) => ({ file }))}
                    limit={3}
                    onDismiss={() => {
                      /* empty function for read only token */
                    }}
                    alignment="horizontal"
                    showFileThumbnail={true}
                    i18nStrings={fileTokenGroupI18nStrings}
                  />
                )}
              </SpaceBetween>
            </ChatBubble>

            {/* {message.showFeedbackDialog && (
              <div className="other-content-vertically-align">
                <FeedbackDialog
                  onDismiss={() => setShowFeedbackDialog(index, false)}
                  onSubmit={() => {
                    setShowFeedbackDialog(index, false);
                    addMessage(index + 1, {
                      type: "chat-bubble",
                      authorId: "gen-ai",
                      content:
                        "Your feedback has been submitted. Thank you for your additional feedback.",
                      timestamp: new Date().toLocaleTimeString(),
                      hideAvatar: true,
                    });
                  }}
                />
              </div>
            )} */}

            {latestMessage.type === "chat-bubble" &&
              latestMessage.supportPrompts &&
              index === messages.length - 1 && (
                <div className="other-content-vertically-align">
                  {message.supportPrompts}
                </div>
              )}
          </SpaceBetween>
        );
      })}
    </div>
  );
}
