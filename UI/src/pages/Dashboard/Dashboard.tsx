import { Container } from "@cloudscape-design/components";
import KPIContainer from "../../components/KPIContainer";

const DashboardPage = () => {
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
  return (
    // <Box padding={"s"}>
    //   <SpaceBetween size="l">
    <Container fitHeight>
      <KPIContainer kpiData={kpiData} />
    </Container>
    //   </SpaceBetween>
    // </Box>
  );
};

export default DashboardPage;
