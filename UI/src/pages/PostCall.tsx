import { useEffect, useRef, useState } from "react";
import { StatCard } from "../components/KPIContainer";
import GenAIPage from "./Home/Home";
import {
  Button,
  SpaceBetween,
  Box,
  Container,
  Grid,
} from "@cloudscape-design/components";
import { useSearchParams } from "react-router-dom";
import { getKPIData } from "../api/api-service";

const PostCall = () => {
  const [isNewChat, setIsNewChat] = useState<boolean>(false);

  const [searchParams] = useSearchParams();
  const sessionIdFromUrl = searchParams.get("session");
  const [kpiData, setKpiData] = useState({
    action_items_pending: 0,
    followups_sent_last_30d: 0,
    sample_request_qty_30d: 0,
    total_hcp_contacted_today: 0,
  });
  const didFetch = useRef(false);
  const handleNewChat = () => {
    localStorage.removeItem("token");
    localStorage.removeItem("sessionId");
    setIsNewChat(true);
  };
  useEffect(() => {
    if (didFetch.current) return;
    didFetch.current = true;

    getKPIData().then((res) => {
      setKpiData(res?.post_call_kpis);
    });
  }, []);

  useEffect(() => {
    if (sessionIdFromUrl) setIsNewChat(true);
    else if (searchParams.get("new-chat") == "true") handleNewChat();
  }, [searchParams]);

  return (
    <>
      {!isNewChat && (
        <>
          <SpaceBetween direction="vertical" size="s">
            <Grid
              gridDefinition={[
                { colspan: { default: 12, xs: 12, s: 3, l: 3 } },
                { colspan: { default: 12, xs: 12, s: 3, l: 3 } },
                { colspan: { default: 12, xs: 12, s: 3, l: 3 } },
                { colspan: { default: 12, xs: 12, s: 3, l: 3 } },
              ]}
            >
              <Box key={"s0"} padding={"n"}>
                <StatCard
                  statData={{
                    kpiName: "Pending Actions",
                    score: kpiData?.action_items_pending,
                  }}
                  index={1}
                />
              </Box>
              <Box key={"s1"} padding={"n"}>
                <StatCard
                  statData={{
                    kpiName: "Followup Sent in 30 Days",
                    score: kpiData?.followups_sent_last_30d,
                  }}
                  index={2}
                />
              </Box>
              <Box key={"s2"} padding={"n"}>
                <StatCard
                  statData={{
                    kpiName: "Sample Requests",
                    score: kpiData?.sample_request_qty_30d,
                  }}
                  index={3}
                />
              </Box>
              <Box key={"s3"} padding={"n"}>
                <StatCard
                  statData={{
                    kpiName: "Contacted HCPs",
                    score: kpiData?.total_hcp_contacted_today,
                  }}
                  index={4}
                />
              </Box>
            </Grid>
            <Container>
              <SpaceBetween direction="vertical" size="s">
                <SpaceBetween direction="vertical" size="xxs">
                  {/* <Box variant="small">March 10, 2023</Box> */}
                  <Box variant="h2">Post-Call</Box>
                </SpaceBetween>
                Capture call outcomes effortlessly using voice-to-CRM
                automation. The system transcribes your summary, structures
                compliant notes, identifies follow-up tasks, and drafts approved
                communications while tracking sentiment and relationship trends.
                <Button onClick={handleNewChat}>Start Querying</Button>
              </SpaceBetween>
            </Container>
          </SpaceBetween>
        </>
      )}
      {isNewChat && (
        <GenAIPage heading="Post-Call" setIsNewChat={setIsNewChat} />
      )}
    </>
  );
};

export default PostCall;
