// Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
// SPDX-License-Identifier: MIT-0
import { useEffect, useRef, useState } from "react";

import Container from "@cloudscape-design/components/container";
import PromptInput from "@cloudscape-design/components/prompt-input";

import {
  getInitialMessages,
  getLoadingMessage,
  type Message,
} from "../../config";

import "../../chat.scss";
import { useStore } from "../../store";
import Header from "@cloudscape-design/components/header";
import { ScrollableContainer } from "../../components/Common";
import Messages from "../../components/Message";
import {
  Box,
  Button,
  ButtonGroup,
  SpaceBetween,
} from "@cloudscape-design/components";
import { downloadPdf } from "../../api/downloadpdf";
import { streamAgent } from "../../services/agentInvocationService";
import {
  addChatToSession,
  createChatSession,
  getChatDetails,
} from "../../services/chatServices";
import { generateSessionId } from "../../api/utils";
import { useAuth } from "../../context/AuthContext";
import { useNavigate, useSearchParams } from "react-router-dom";
import LogModal from "../../components/LogModal";

interface ChatPageProps {
  heading: string;
  setIsNewChat: (isNewChat: boolean) => void;
}

const GenAIPage = ({ heading, setIsNewChat }: ChatPageProps) => {
  // const waitTimeBeforeLoading = 1000;
  const {
    state,
    actions: {
      setHelpPanelData,
      setToolsTab,
      setHelpPanelTopic,
      setToolsOpen,
      setModuleSelected,
    },
  } = useStore();
  // The loading state will be shown for 4 seconds for loading prompt and 1.5 seconds for rest of the prompts
  // const waitTimeBeforeResponse = (isLoadingPrompt: boolean = false) =>
  //   isLoadingPrompt ? 4000 : 1500;

  const [prompt, setPrompt] = useState("");
  const [isGenAiResponseLoading] = useState(false);
  const messagesContainerRef = useRef<HTMLDivElement>(null);
  // const [currentMessage, setCurrentMessage] = useState("");
  const { user } = useAuth();
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const sessionIdParam = searchParams.get("session");
  const [sessionId, setSessionId] = useState<string>(sessionIdParam || "");
  const [logResponse, setLogResponse] = useState<string>("");
  const [showModal, setShowModal] = useState<boolean>(false);

  // const [files, setFiles] = useState<File[]>([]);
  const promptInputRef = useRef<HTMLTextAreaElement>(null);
  const [messages, setMessages] = useState<Message[]>([]);

  const lastMessageContent = messages.length
    ? messages[messages.length - 1]?.content
    : "";

  useEffect(() => {
    setMessages(getInitialMessages(state.moduleSelected));
    setHelpPanelData(null);
    setHelpPanelTopic("");
    setToolsOpen(false);
    setToolsTab("no-help");
    const moduleName = heading.replace(" ", "-").toLowerCase();
    setModuleSelected(moduleName);
    // setMessages([]);
    // setCurrentMessage("");
  }, [heading, state.moduleSelected]);

  useEffect(() => {
    // Scroll to the bottom to show the new/latest message
    setTimeout(() => {
      if (messagesContainerRef.current) {
        messagesContainerRef.current.scrollTop =
          messagesContainerRef.current.scrollHeight;
      }
    }, 0);
  }, [lastMessageContent]);

  useEffect(() => {
    const sessionIdFromUrl = searchParams.get("session");

    if (!sessionIdFromUrl) return;

    setMessages([]);

    setSessionId(sessionIdFromUrl);
    localStorage.setItem("sessionId", sessionIdFromUrl);

    // Fetch chat details
    const loadChat = async () => {
      try {
        if (user && user.username) {
          const chat = await getChatDetails(sessionIdFromUrl, user?.username);
          if (chat?.messages) {
            setMessages(
              chat.messages.map((m: any) => ({
                type: "chat-bubble",
                authorId: m.role === "assistant" ? "gen-ai" : "user",
                content: m.content,
                timestamp: m.created_at,
              }))
            );
          }
        }
      } catch (err: any) {
        console.error("Error loading chat:", err);
      }
    };

    loadChat();
  }, [searchParams, user?.username]);

  // useEffect(()=>{
  //   updateChat();
  // },[messages])
  // Add placeholder for streaming response and track its index
  let botMessageIndex = -1;

  let fullResponse = "";
  let logData = "";
  const onPromptSend = async ({
    detail: { value },
  }: {
    detail: { value: string };
  }) => {
    setLogResponse("");
    let curSessionId = sessionId;
    if (!localStorage.getItem("sessionId")) {
      console.log("new session created");
      curSessionId = generateSessionId(33);
      setSessionId(curSessionId);
      const obj = {
        session_id: curSessionId,
        agent_id: heading.replace("-", "").toLowerCase(),
        title: value.length > 20 ? value.slice(0, 20) + "..." : value,
        user_id: user?.username,
      };
      createChatSession(obj);
      localStorage.setItem("sessionId", curSessionId);
    }
    // else{
    //   const payload = {
    //   session_id: sessionId,
    //   user_id: user?.username,
    //   role: 'user',
    //   content: value
    // };
    //   addChatToSession(payload);
    // }

    const newMessage: Message = {
      type: "chat-bubble",
      authorId: "user-john-due",
      content: value,
      timestamp: new Date().toLocaleTimeString(),
    };

    setMessages((prevMessages) => [...prevMessages, newMessage]);
    const msgObj = {
      session_id: curSessionId,
      content: value,
      user_id: user?.username,
      role: "user",
    };
    addChatToSession(msgObj);
    setPrompt("");
    setMessages((prev) => {
      botMessageIndex = prev.length;
      return [...prev, getLoadingMessage()];
    });
    try {
      await streamAgent(
        heading.replaceAll("-", "").toLowerCase(),
        prompt,
        curSessionId,
        user?.username,
        (chunk) => {
          if (chunk.indexOf("[LOG]") > -1) {
            logData += chunk + " \n";
            // setLogResponse((prev: any) => prev + chunk);
            setLogResponse((prev: any) => prev + logData);
          } else {
            fullResponse += chunk;

            setMessages((prev) => {
              const updated = [...prev];
              if (botMessageIndex >= 0 && botMessageIndex < updated.length) {
                updated[botMessageIndex] = {
                  type: "chat-bubble",
                  authorId: "gen-ai",
                  content: fullResponse,
                  timestamp: new Date().toLocaleTimeString(),
                };
              }
              return updated;
            });
          }
        }
      );
      const msgObj = {
        session_id: curSessionId,
        content: fullResponse,
        user_id: user?.username,
        role: "assistant",
      };
      addChatToSession(msgObj);
      // saveMessage(currentRunId, fullResponse, "assistant");
    } catch (error) {
      console.error("Streaming error:", error);
      setMessages((prev) => {
        const updated = [...prev];
        if (botMessageIndex >= 0 && botMessageIndex < updated.length) {
          updated[botMessageIndex] = {
            type: "chat-bubble",
            authorId: "gen-ai",
            content: "Unable process now please try after sometime",
            timestamp: new Date().toLocaleTimeString(),
            // files,
          };
        }
        return updated;
      });
    }
  };

  const addMessage = (index: number, message: Message) => {
    setMessages((prevMessages) => {
      const updatedMessages = [...prevMessages];
      updatedMessages.splice(index, 0, message);
      return updatedMessages;
    });
  };

  const handleExport = () => {
    let markDownString = "";
    messages.forEach((msg: any, index: number) => {
      if (index != 0) {
        if (typeof msg.content === "string") {
          markDownString += "**Q’s " + msg.content + "** \n";
        } else if (
          typeof msg.content === "object" &&
          msg.content.props?.children?.props?.children
        ) {
          markDownString += msg.content.props.children.props.children + "\n";
        }
      }
    });
    downloadPdf(markDownString, heading + Date.now());
  };

  return (
    <Container
      fitHeight
      header={
        <Header
          actions={
            <SpaceBetween direction="horizontal" size="xs">
              <Button onClick={handleExport}>Download Chat</Button>
              <Button
                iconName="arrow-left"
                onClick={() => {
                  setIsNewChat(false);
                  navigate(location.pathname, { replace: true });
                }}
              >
                Back
              </Button>
            </SpaceBetween>
          }
        >
          {heading}
        </Header>
      }
      disableContentPaddings
    >
      <>
        {/* {currentMessage && (
          <Box padding={"s"} className="bg-grey">
            {`Q’s: ${currentMessage}`}
          </Box>
        )} */}
        <Container
          data-testid="chat-container"
          variant={"stacked"}
          className="chat-container"
          fitHeight
          disableContentPaddings
          footer={
            <>
              <PromptInput
                // maxRows={8}
                actionButtonIconSvg={
                  <span>
                    <svg
                      data-svg-send
                      xmlns="http://www.w3.org/2000/svg"
                      width="49"
                      height="50"
                      viewBox="0 0 49 50"
                      fill="none"
                    >
                      <rect
                        width="48.3206"
                        height="49.3067"
                        rx="24.1603"
                        fill="#006ADB"
                      />
                      <path
                        d="M16.3594 35.5823C16.3133 35.6902 16.3013 35.8097 16.325 35.9246C16.3487 36.0396 16.407 36.1445 16.4921 36.2253C16.5772 36.3062 16.685 36.3591 16.801 36.3769C16.917 36.3947 17.0357 36.3766 17.1412 36.325L37.8859 26.156C37.984 26.11 38.067 26.0369 38.1251 25.9455C38.1832 25.854 38.2141 25.7478 38.2141 25.6394C38.2141 25.5311 38.1832 25.4249 38.1251 25.3334C38.067 25.2419 37.984 25.1689 37.8859 25.1229L17.1412 14.9539C17.0357 14.9023 16.917 14.8842 16.801 14.902C16.685 14.9198 16.5772 14.9727 16.4921 15.0535C16.407 15.1344 16.3487 15.2393 16.325 15.3543C16.3013 15.4692 16.3133 15.5887 16.3594 15.6966L20.2236 24.7348C20.3459 25.0204 20.4091 25.3278 20.4093 25.6385C20.4096 25.9491 20.347 26.2566 20.2252 26.5424L16.3594 35.5823Z"
                        stroke="white"
                        strokeWidth="2"
                        strokeLinecap="round"
                        strokeLinejoin="round"
                      />
                      <path
                        d="M38.208 25.6401L20.409 25.6393"
                        stroke="white"
                        strokeWidth="1.31485"
                        strokeLinecap="round"
                        strokeLinejoin="round"
                      />
                    </svg>
                  </span>
                }
                minRows={2}
                ref={promptInputRef}
                onChange={({ detail }) => setPrompt(detail.value)}
                onAction={onPromptSend}
                value={prompt}
                actionButtonAriaLabel={
                  isGenAiResponseLoading
                    ? "Send message button - suppressed"
                    : "Send message"
                }
                actionButtonIconName="send"
                ariaLabel={
                  isGenAiResponseLoading
                    ? "Prompt input - suppressed"
                    : "Prompt input"
                }
                placeholder="Ask a question"
                autoFocus
                disableSecondaryActionsPaddings
                secondaryActions={
                  <Box padding={{ left: "xxs", top: "xs" }}>
                    <ButtonGroup
                      ariaLabel="Chat actions"
                      onItemClick={() => setShowModal(true)}
                      items={[
                        {
                          type: "icon-button",
                          id: "copy",
                          iconName: "transcript",
                          text: "All Logs",
                        },
                      ]}
                      variant="icon"
                    />
                  </Box>
                }
              />
            </>
          }
        >
          <ScrollableContainer ref={messagesContainerRef} data-pdf-section>
            <Messages
              messages={messages}
              // setShowFeedbackDialog={setShowFeedbackDialog}
              addMessage={addMessage}
            />
          </ScrollableContainer>
        </Container>
      </>
      {showModal && (
        <LogModal
          content={logResponse}
          showModal={showModal}
          setShowModal={setShowModal}
        />
      )}
    </Container>
  );
};

export default GenAIPage;
