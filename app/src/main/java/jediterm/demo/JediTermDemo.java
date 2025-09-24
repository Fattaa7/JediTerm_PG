package jediterm.demo;

import com.jediterm.terminal.ui.JediTermWidget;
import com.jediterm.terminal.ui.settings.DefaultSettingsProvider;
import com.jediterm.terminal.TtyConnector;
import com.jediterm.pty.PtyProcessTtyConnector;
import com.pty4j.PtyProcess;
import com.pty4j.PtyProcessBuilder;

import javax.swing.*;
import java.awt.*;
import java.io.IOException;
import java.io.OutputStream;
import java.nio.charset.Charset;

public class JediTermDemo {

    public static void main(String[] args) {
        SwingUtilities.invokeLater(() -> {
            try {
                JFrame frame = new JFrame("My App with Terminal");
                frame.setDefaultCloseOperation(JFrame.EXIT_ON_CLOSE);
                frame.setSize(1000, 700);

                // Create tabbed pane
                JTabbedPane tabbedPane = new JTabbedPane();

                // Terminal tab
                JediTermWidget terminal = createTerminal();
                tabbedPane.addTab("Terminal", terminal);

                // Placeholder tabs for your future app
                JPanel dashboardPanel = new JPanel(new BorderLayout());
                dashboardPanel.add(new JLabel("Dashboard content goes here", SwingConstants.CENTER),
                        BorderLayout.CENTER);
                tabbedPane.addTab("Dashboard", dashboardPanel);

                JPanel logsPanel = new JPanel(new BorderLayout());
                logsPanel.add(new JLabel("Logs will appear here", SwingConstants.CENTER), BorderLayout.CENTER);
                tabbedPane.addTab("Logs", logsPanel);

                // Add tabs to frame
                frame.add(tabbedPane, BorderLayout.CENTER);
                frame.setVisible(true);

            } catch (IOException e) {
                e.printStackTrace();
            }
        });
    }

    private static JediTermWidget createTerminal() throws IOException {
        DefaultSettingsProvider settingsProvider = new DefaultSettingsProvider();

        String path = "C:\\Users\\ahmed\\OneDrive\\Documents\\Java_prjs\\JediTerm";
        JediTermWidget terminal = new JediTermWidget(80, 24, settingsProvider);

        String[] command;
        if (System.getProperty("os.name").toLowerCase().contains("win")) {
            // Run cmd and immediately execute your startup commands
            command = new String[] {
                    "cmd.exe", "/K", "cd " + path + "&& gemini"
            };
        } else {
            // For Linux/macOS: bash -i -c "cd .. && gemini; exec bash"
            command = new String[] { "/bin/bash", "-i", "-c", "cd .. && gemini; exec bash" };
        }

        PtyProcess process = new PtyProcessBuilder(command)
                .setRedirectErrorStream(true)
                .start();

        TtyConnector connector = new PtyProcessTtyConnector(process, Charset.defaultCharset());
        terminal.setTtyConnector(connector);
        terminal.start();

        return terminal;
    }

}
