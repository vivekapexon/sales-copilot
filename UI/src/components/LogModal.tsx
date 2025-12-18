import { SpaceBetween, Button, Box } from "@cloudscape-design/components";
import Modal from "@cloudscape-design/components/modal";
import Markdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { downloadPdf } from "../api/downloadpdf";

interface LogModalProps {
  content: any;
  setShowModal: (showModal: boolean) => void;
  showModal: boolean;
}
const LogModal = ({ content, showModal, setShowModal }: LogModalProps) => {
  return (
    <Modal
      onDismiss={() => setShowModal(false)}
      visible={showModal}
      footer={
        <Box float="right">
          <SpaceBetween direction="horizontal" size="xs">
            <Button variant="link" onClick={() => setShowModal(false)}>
              Cancel
            </Button>
            <Button variant="primary" onClick={() => setShowModal(false)}>
              Ok
            </Button>
          </SpaceBetween>
        </Box>
      }
      header={
        <Box>
          <SpaceBetween direction="horizontal" size="s">
            <Box variant="h2">All Logs</Box>
            {content && content.length > 0 && (
              <Box textAlign="right" float="right">
                <Button
                  variant="icon"
                  iconName="download"
                  onClick={() => downloadPdf(content, "log" + Date.now())}
                />
              </Box>
            )}
          </SpaceBetween>
        </Box>
      }
    >
      <div className="modal-log">
        <Markdown remarkPlugins={[remarkGfm]}>
          {content && content.length ? content : "No Logs to Display"}
        </Markdown>
      </div>
    </Modal>
  );
};

export default LogModal;
