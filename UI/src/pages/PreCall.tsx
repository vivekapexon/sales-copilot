import { useEffect, useState } from "react";
import KPIContainer from "../components/KPIContainer";
import GenAIPage from "./Home/Home";
import {
  Button,
  SpaceBetween,
  Box,
  Container,
} from "@cloudscape-design/components";
import { useSearchParams } from "react-router-dom";
declare const html2pdf: any;

const PreCall = () => {
  const [isNewChat, setIsNewChat] = useState<boolean>(false);
  const [searchParams] = useSearchParams();
  const sessionIdFromUrl = searchParams.get("session");

  const kpiData = [
    {
      kpiName: "Total Activities",
      score: "50",
      statMessage: "+67% vs. baseline",
      trendup: "up",
    },
    {
      kpiName: "Critical Threats",
      score: "4",
      statMessage: "Vertex dominance",
      trendup: "up",
    },
    {
      kpiName: "Strategies Generated",
      score: "8",
      statMessage: "Multi-tier response",
      trendup: "up",
    },
    {
      kpiName: "Overall Threat Level",
      score: "Critical",
      statMessage: "Max threat score: 10",
      trendup: "up",
    },
  ];

  const handleNewChat = () => {
    localStorage.removeItem("token");
    localStorage.removeItem("sessionId");
    setIsNewChat(true);
  };

  useEffect(() => {
    if (sessionIdFromUrl) setIsNewChat(true);
  }, [searchParams]);

  // const getUserSessions = () => {
  //   const response = getSessions("precall");
  //   response.then((res) => {
  //     console.log(res);
  //     // setChatHistoryList(res.sessions);
  //   });
  // };

  return (
    <>
      {!isNewChat && (
        <>
          <SpaceBetween direction="vertical" size="s">
            <KPIContainer kpiData={kpiData} />
            <Container>
              <SpaceBetween direction="vertical" size="s">
                <SpaceBetween direction="vertical" size="xxs">
                  {/* <Box variant="small">March 10, 2023</Box> */}
                  <Box variant="h2">Pre-Call</Box>
                </SpaceBetween>
                This is a paragraph. Lorem ipsum dolor sit amet, consectetur
                adipiscing elit. Ut luctus tempor dolor ac accumsan. This is a
                paragraph. Lorem ipsum dolor sit amet, consectetur adipiscing
                elit. Ut luctus tempor dolor ac accumsan.
                <Button onClick={handleNewChat}>Start Querying</Button>
              </SpaceBetween>
            </Container>
          </SpaceBetween>
        </>
      )}
      {isNewChat && (
        <GenAIPage heading="Pre-Call" setIsNewChat={setIsNewChat} />
      )}
    </>
  );
};

export default PreCall;
