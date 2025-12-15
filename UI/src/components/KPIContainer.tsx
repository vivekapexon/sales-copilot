import { Container, Box, Grid } from "@cloudscape-design/components";

// import criticalThreatSVG from "../../../../assets/critical-threat.svg";
// import totalActivitiesSVG from "../../../../assets/total-activities.svg";
// import stratergiesSVG from "../../../../assets/stratergies.svg";
// import threatLevelSVG from "../../../../assets/threat-level.svg";

interface StatCardProps {
  statData: any;
  index: number;
}

export const StatCard = ({ statData }: StatCardProps) => {
  return (
    <Container fitHeight>
      <Box>
        <Grid
          gridDefinition={
            [
              // { colspan: { default: 7, xs: 7, s: 9, l: 9 } },
              // { colspan: { default: 5, xs: 5, s: 3, l: 3 } },
            ]
          }
        >
          <Box variant="h3" fontSize="body-m">
            {statData.kpiName}
          </Box>
          <Box>{/* <img src={getIcon(index.toString())} /> */}</Box>
        </Grid>
        <Box variant="h1" padding={"n"} fontSize="heading-xl">
          {statData.score}
        </Box>
        {/* {statData.trendup == "up" && (
          <Box variant="p" padding={"xs"} color={"text-status-success"}>
            <TrendingUp
              style={{ verticalAlign: "middle" }}
              alignmentBaseline="middle"
              className="mr-1 h-4 w-4"
            />{" "}
            {statData.statMessage}
          </Box>
        )}
        {statData.trendup != "up" && (
          <Box variant="p" padding={"xs"} color={"text-status-error"}>
            <TrendingDown
              style={{ verticalAlign: "middle" }}
              className="mr-1 h-4 w-4"
            />{" "}
            {statData.statMessage}
          </Box>
        )} */}
      </Box>
    </Container>
  );
};

export default function KPIContainer({ kpiData }: any) {
  return (
    <Grid
      gridDefinition={[
        { colspan: { default: 12, xs: 12, s: 3, l: 3 } },
        { colspan: { default: 12, xs: 12, s: 3, l: 3 } },
        { colspan: { default: 12, xs: 12, s: 3, l: 3 } },
        { colspan: { default: 12, xs: 12, s: 3, l: 3 } },
      ]}
    >
      {kpiData?.map((stat: any, index: number) => (
        <Box key={index} padding={"n"}>
          <StatCard statData={stat} index={index} />
        </Box>
      ))}
    </Grid>
  );
}
