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
declare const html2pdf: any;

const PreCall = () => {
  const [isNewChat, setIsNewChat] = useState<boolean>(false);
  const [searchParams] = useSearchParams();
  const sessionIdFromUrl = searchParams.get("session");
  const [kpiData, setKpiData] = useState({
    total_hcps: 0,
    total_interacted_hcps: 0,
    followup_emails_sent: 0,
    scheduled_calls_next_7d: 0,
  });
  const didFetch = useRef(false);

  const handleNewChat = () => {
    localStorage.removeItem("token");
    localStorage.removeItem("sessionId");
    setIsNewChat(true);
  };

  useEffect(() => {
    if (sessionIdFromUrl) setIsNewChat(true);
    else if (searchParams.get("new-chat") == "true") handleNewChat();
  }, [searchParams]);

  useEffect(() => {
    if (didFetch.current) return;
    didFetch.current = true;

    getKPIData().then((res) => {
      setKpiData(res?.pre_call_kpis);
    });
  }, []);

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
                    kpiName: "Total HCPs",
                    score: kpiData?.total_hcps,
                  }}
                  index={1}
                />
              </Box>
              <Box key={"s1"} padding={"n"}>
                <StatCard
                  statData={{
                    kpiName: "Followup Email Sent",
                    score: kpiData?.followup_emails_sent,
                  }}
                  index={2}
                />
              </Box>
              <Box key={"s2"} padding={"n"}>
                <StatCard
                  statData={{
                    kpiName: "Scheduled Calls",
                    score: kpiData?.scheduled_calls_next_7d,
                  }}
                  index={3}
                />
              </Box>
              <Box key={"s3"} padding={"n"}>
                <StatCard
                  statData={{
                    kpiName: "Interacted HCPs",
                    score: kpiData?.total_interacted_hcps,
                  }}
                  index={4}
                />
              </Box>
            </Grid>
            <Container>
              <SpaceBetween direction="vertical" size="s">
                <SpaceBetween direction="vertical" size="xxs">
                  {/* <Box variant="small">March 10, 2023</Box> */}
                  <Box variant="h2">Pre-Call</Box>
                </SpaceBetween>
                Prepare instantly with AI-driven insights that unify HCP
                history, prescribing trends, access updates, and recent
                engagements. The system delivers concise call briefs with clear
                objectives, personalized talking points, and anticipated
                objections—helping you enter every interaction fully prepared.
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
